"""Run Solar matcher on EXP-011 gate-failed artifacts (diagnostic use only).

EXP-011 artifacts (actionable_only, identity_only) are schema-valid (15/15 each)
but failed the pre-registered completeness gate (3 issues per condition vs. ≤2
allowed). The matcher was never run. This script runs matching for archival and
planning purposes — results are NOT confirmatory and must NOT be reported as such.

Output: runs/confirmatory/matches_exp011_diagnostic/
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

from scripts.llm_matcher import (
    STAGES,
    MANIFEST_PATH,
    PERSONA_DATA_PATH,
    SolarMatcher,
    StageMatch,
    compute_accuracy,
    load_personas,
    match_one_run,
)

ABLATION_ACTIONABLE = ROOT / "runs" / "ablation" / "actionable_only"
ABLATION_IDENTITY = ROOT / "runs" / "ablation" / "identity_only"
DEFAULT_OUTPUT = ROOT / "runs" / "confirmatory" / "matches_exp011_diagnostic"


def run_ablation_dir(
    artifact_dir: Path,
    condition: str,
    output_dir: Path,
    manifest: dict,
    personas_by_id: dict,
    matcher: SolarMatcher | None,
    dry_run: bool = False,
    resume: bool = False,
) -> list[StageMatch]:
    artifact_paths = sorted(artifact_dir.glob("*_artifacts.json"))
    cond_output = output_dir / condition
    cond_output.mkdir(parents=True, exist_ok=True)
    all_results: list[StageMatch] = []

    for artifact_path in artifact_paths:
        run_id = artifact_path.stem.replace("_artifacts", "")
        out_path = cond_output / f"{run_id}_match.json"

        if resume and out_path.exists():
            print(f"SKIP (resume) {run_id}")
            existing = [StageMatch(**r) for r in json.loads(out_path.read_text())]
            all_results.extend(existing)
            continue

        print(f"\n{'='*60}\n[{condition}] {run_id}")
        try:
            results = match_one_run(
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
        description="Diagnostic matcher run on EXP-011 gate-failed artifacts"
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--condition",
        choices=["actionable_only", "identity_only", "both"],
        default="both",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    personas_by_id = load_personas(PERSONA_DATA_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text())

    matcher: SolarMatcher | None = None
    if not args.dry_run:
        matcher = SolarMatcher()

    print("WARNING: EXP-011 artifacts failed the pre-registered completeness gate.")
    print("Results are DIAGNOSTIC ONLY — do not use as confirmatory evidence.")
    print(f"Output: {args.output_dir}")

    t0 = time.monotonic()
    all_results: list[StageMatch] = []

    conditions = []
    if args.condition in ("actionable_only", "both"):
        conditions.append(("actionable_only", ABLATION_ACTIONABLE))
    if args.condition in ("identity_only", "both"):
        conditions.append(("identity_only", ABLATION_IDENTITY))

    for condition, artifact_dir in conditions:
        results = run_ablation_dir(
            artifact_dir=artifact_dir,
            condition=condition,
            output_dir=args.output_dir,
            manifest=manifest,
            personas_by_id=personas_by_id,
            matcher=matcher,
            dry_run=args.dry_run,
            resume=args.resume,
        )
        acc = compute_accuracy(results)
        print(f"\n[{condition}] Acc@1 (n={acc['n']} per stage, DIAGNOSTIC):")
        print(f"  Plan={acc['plan']:.3f}  Search={acc['search']:.3f}  "
              f"Comp={acc['compress']:.3f}  Write={acc['write']:.3f}")

        summary_path = args.output_dir / condition / f"{condition}_summary.json"
        if not args.dry_run:
            summary_path.write_text(json.dumps(acc, indent=2), encoding="utf-8")
        all_results.extend(results)

    elapsed = time.monotonic() - t0
    print(f"\nTotal elapsed: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
