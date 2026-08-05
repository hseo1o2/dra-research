"""Run Solar matching with BOTH artifact-side AND candidate-side identity removal.

Experiment: tests whether persona attribution is still above chance when
identity information is removed from both artifacts (pre-masked by the
run_identifier_masking pipeline) AND from candidate profiles (Basic Attributes
excluded). This is the most conservative test of whether preference-level
discourse features alone support attribution.

Artifacts: identity-masked artifacts from masked_identity_hardneg_v1/ (both seeds, n=120)
Candidates: identity-stripped profiles (Basic Attributes excluded)
Output: runs/confirmatory/matches_dual_masked/

Usage:
    python scripts/run_dual_masked.py --dry-run
    python scripts/run_dual_masked.py
    python scripts/run_dual_masked.py --resume
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import scripts.llm_matcher as llm_matcher
from scripts.llm_matcher import (
    STAGES,
    MANIFEST_PATH,
    PERSONA_DATA_PATH,
    SolarMatcher,
    StageMatch,
    compute_accuracy,
    load_personas,
)

# ---------------------------------------------------------------------------
# Candidate-side identity stripping (same as run_candidate_profile_masked.py)
# ---------------------------------------------------------------------------

_ACTIONABLE_SECTIONS = [
    "Behavioral Characteristics",
    "Personality Traits",
    "Preferences and Interests",
    "Environment",
]


def format_persona_no_identity(persona: dict) -> str:
    lines: list[str] = []
    for section in _ACTIONABLE_SECTIONS:
        content = persona.get(section)
        if content is None:
            continue
        lines.append(f"=== {section} ===")
        lines.extend(llm_matcher._flatten_dict(content))
    return "\n".join(lines)


llm_matcher.format_persona = format_persona_no_identity

# ---------------------------------------------------------------------------
# Artifact source: pre-masked artifacts (identity strings removed from text)
# ---------------------------------------------------------------------------

MASKED_ARTIFACT_DIR = ROOT / "runs" / "confirmatory" / "masked_identity_hardneg_v1"
DEFAULT_OUTPUT = ROOT / "runs" / "confirmatory" / "matches_dual_masked"


def run_batch(
    artifact_dir: Path,
    output_dir: Path,
    manifest: dict,
    personas_by_id: dict,
    matcher: SolarMatcher | None,
    dry_run: bool = False,
    resume: bool = False,
) -> list[StageMatch]:
    # Masked artifact files end in _artifacts.json (not _masked_artifacts.json)
    artifact_paths = sorted(artifact_dir.glob("pilot_*_artifacts.json"))
    output_dir.mkdir(parents=True, exist_ok=True)
    all_results: list[StageMatch] = []

    for artifact_path in artifact_paths:
        run_id = artifact_path.stem.replace("_artifacts", "")
        out_path = output_dir / f"{run_id}_match.json"

        if resume and out_path.exists():
            print(f"SKIP (resume) {run_id}")
            existing = [StageMatch(**r) for r in json.loads(out_path.read_text())]
            all_results.extend(existing)
            continue

        print(f"\n{'='*60}\n{run_id}")
        try:
            results = llm_matcher.match_one_run(
                run_id=run_id,
                artifact_path=artifact_path,
                manifest=manifest,
                personas_by_id=personas_by_id,
                matcher=matcher,
                stages=STAGES,
                dry_run=dry_run,
            )
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue

        if not dry_run:
            out_path.write_text(
                json.dumps([asdict(r) for r in results], indent=2),
                encoding="utf-8",
            )
        all_results.extend(results)

    return all_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dual-masked: identity-removed artifacts + identity-stripped candidate profiles"
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    personas_by_id = load_personas(PERSONA_DATA_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text())

    matcher: SolarMatcher | None = None
    if not args.dry_run:
        matcher = SolarMatcher()

    print("Dual-masked experiment:")
    print("  Artifacts: identity-masked (masked_identity_hardneg_v1/)")
    print("  Candidates: actionable sections only (Basic Attributes excluded)")
    print(f"  Output: {args.output_dir}")

    t0 = time.monotonic()
    results = run_batch(
        artifact_dir=MASKED_ARTIFACT_DIR,
        output_dir=args.output_dir,
        manifest=manifest,
        personas_by_id=personas_by_id,
        matcher=matcher,
        dry_run=args.dry_run,
        resume=args.resume,
    )
    elapsed = time.monotonic() - t0

    if results:
        acc = compute_accuracy(results)
        print(f"\n{'='*60}")
        print(f"Dual-masked Solar Acc@1  (n={acc['n']} per stage)")
        print(f"  Plan={acc['plan']:.3f}  Search={acc['search']:.3f}  "
              f"Comp={acc['compress']:.3f}  Write={acc['write']:.3f}")
        print(f"  Chance={acc['chance']:.3f}  Macro={acc['macro_avg']:.3f}")
        print(f"Elapsed: {elapsed:.0f}s")

        summary_path = args.output_dir / "dual_masked_summary.json"
        if not args.dry_run:
            summary_path.write_text(json.dumps(acc, indent=2), encoding="utf-8")
            print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
