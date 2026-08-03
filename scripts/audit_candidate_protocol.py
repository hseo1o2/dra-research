"""Audit recorded matcher candidates against the frozen per-GT manifest sets.

Network-free. Existing outputs are not modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.candidate_protocol import lookup_pdr_candidates

DEFAULT_MATCH_DIR = ROOT / "runs" / "confirmatory" / "matches_sha256"
DEFAULT_OUTPUT = (
    ROOT / "runs" / "confirmatory" / "candidate_protocol_audit.json"
)


def audit(
    manifest: dict[str, Any],
    match_dir: Path,
) -> dict[str, Any]:
    files = sorted(match_dir.glob("*_match.json"))
    rows: list[dict[str, Any]] = []
    for path in files:
        records = json.loads(path.read_text(encoding="utf-8"))
        if not records:
            continue
        run_id = str(records[0]["run_id"])
        _, expected = lookup_pdr_candidates(run_id, manifest)
        recorded_sets = {
            tuple(sorted(row["candidate_userids"])) for row in records
        }
        if len(recorded_sets) != 1:
            raise ValueError(f"Inconsistent stage candidates in {path}")
        recorded = list(next(iter(recorded_sets)))
        rows.append({
            "run_id": run_id,
            "expected_candidates": expected,
            "recorded_candidates": recorded,
            "set_matches": set(expected) == set(recorded),
            "stages": len(records),
        })
    mismatches = [row for row in rows if not row["set_matches"]]
    return {
        "schema_version": 1,
        "external_api_calls": 0,
        "match_dir": str(match_dir),
        "run_files": len(rows),
        "matching_candidate_sets": len(rows) - len(mismatches),
        "mismatching_candidate_sets": len(mismatches),
        "passed": bool(rows) and not mismatches,
        "mismatch_examples": mismatches[:10],
        "interpretation": (
            "A failing audit means the recorded matcher outputs do not "
            "implement the manifest's per-GT hard-negative protocol."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "manifest.json"
    )
    parser.add_argument("--match-dir", type=Path, default=DEFAULT_MATCH_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = audit(manifest, args.match_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "passed": result["passed"],
        "run_files": result["run_files"],
        "matching": result["matching_candidate_sets"],
        "mismatching": result["mismatching_candidate_sets"],
        "output": str(args.output),
    }, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
