"""Re-run Solar matching with 'background' removed from system prompt.

Experiment: the current system prompt instructs the matcher to focus on
'content priorities, framing, vocabulary, and topic angles that reflect
the user's background, goals, and preferences.' 'background' directly
targets identity-layer cues. This ablation removes the word to test
whether identity-shell dominance is partly prompt-induced.

Artifacts: original (unmasked) confirmatory artifacts
Candidates: full persona profiles (unchanged)
System prompt: 'background' removed
Output: runs/confirmatory/matches_prompt_no_background/

Usage:
    python scripts/run_prompt_background_removed.py --dry-run
    python scripts/run_prompt_background_removed.py
    python scripts/run_prompt_background_removed.py --resume
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
    _lookup_manifest,
)

# ---------------------------------------------------------------------------
# Modified system prompt: 'background' removed
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_NO_BACKGROUND = (
    "You are an expert document analyst specializing in user profiling. "
    "Given a document excerpt from a research report and a set of candidate user profiles, "
    "identify which user this document was most likely produced for. "
    "Focus on content priorities, framing, vocabulary, and topic angles "
    "that reflect the user's goals and preferences. "
    "Call submit_attribution with your answer."
)

llm_matcher.SYSTEM_PROMPT = SYSTEM_PROMPT_NO_BACKGROUND

ARTIFACT_DIR = ROOT / "runs" / "confirmatory"
DEFAULT_OUTPUT = ROOT / "runs" / "confirmatory" / "matches_prompt_no_background"


def run_batch(
    artifact_dir: Path,
    output_dir: Path,
    manifest: dict,
    personas_by_id: dict,
    matcher: SolarMatcher | None,
    seed: int | None = None,
    dry_run: bool = False,
    resume: bool = False,
) -> list[StageMatch]:
    artifact_paths = sorted(artifact_dir.glob("*_artifacts.json"))
    if seed is not None:
        artifact_paths = [p for p in artifact_paths if f"_seed{seed}_" in p.stem]

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
        description="Matching with 'background' removed from system prompt"
    )
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    personas_by_id = load_personas(PERSONA_DATA_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text())

    matcher: SolarMatcher | None = None
    if not args.dry_run:
        matcher = SolarMatcher()

    print(f"System prompt: 'background' removed")
    print(f"Candidates: full profiles (unchanged)")
    print(f"Output: {args.output_dir}")

    t0 = time.monotonic()
    results = run_batch(
        artifact_dir=args.artifact_dir,
        output_dir=args.output_dir,
        manifest=manifest,
        personas_by_id=personas_by_id,
        matcher=matcher,
        seed=args.seed,
        dry_run=args.dry_run,
        resume=args.resume,
    )
    elapsed = time.monotonic() - t0

    if results:
        acc = compute_accuracy(results)
        print(f"\n{'='*60}")
        print(f"No-background-prompt Solar Acc@1  (n={acc['n']} per stage)")
        print(f"  Plan={acc['plan']:.3f}  Search={acc['search']:.3f}  "
              f"Comp={acc['compress']:.3f}  Write={acc['write']:.3f}")
        print(f"  Chance={acc['chance']:.3f}  Macro={acc['macro_avg']:.3f}")
        print(f"Elapsed: {elapsed:.0f}s")

        summary_path = args.output_dir / "prompt_no_background_summary.json"
        if not args.dry_run:
            summary_path.write_text(json.dumps(acc, indent=2), encoding="utf-8")
            print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
