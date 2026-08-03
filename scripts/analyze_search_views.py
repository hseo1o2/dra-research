"""Paired, task-clustered analysis of Search artifact view controls.

This script is network-free. It compares the full Search artifact with
query-only and snippet-only Solar matcher outputs for the same reports.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_matches import _exact_mcnemar_p, _percentile
DEFAULT_FULL = ROOT / "runs" / "confirmatory" / "matches_hardneg_v1"
DEFAULT_QUERIES = (
    ROOT / "runs" / "confirmatory"
    / "search_view_queries_hardneg_v1_matches"
)
DEFAULT_SNIPPETS = (
    ROOT / "runs" / "confirmatory"
    / "search_view_snippets_hardneg_v1_matches"
)
DEFAULT_OUTPUT = (
    ROOT / "runs" / "confirmatory" / "analysis_search_views_hardneg_v1"
    / "search_view_summary.json"
)
RUN_PATTERN = re.compile(r"_task(?P<taskid>\d+)_.*_seed(?P<seed>\d+)$")


def load_search_matches(directory: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*_match.json")):
        for raw in json.loads(path.read_text(encoding="utf-8")):
            if raw["stage"] != "search":
                continue
            match = RUN_PATTERN.search(raw["run_id"])
            if match is None:
                raise ValueError(f"Cannot parse run ID: {raw['run_id']}")
            rows.append({
                **raw,
                "taskid": int(match.group("taskid")),
                "seed": int(match.group("seed")),
                "correct": bool(raw["correct"]),
            })
    return rows


def _cluster_interval(
    paired: list[dict[str, Any]], repetitions: int, seed: int
) -> tuple[float, float]:
    by_task: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in paired:
        by_task[row["taskid"]].append(row)
    taskids = sorted(by_task)
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(repetitions):
        sample: list[dict[str, Any]] = []
        for taskid in rng.choices(taskids, k=len(taskids)):
            sample.extend(by_task[taskid])
        estimates.append(
            sum(row["difference"] for row in sample) / len(sample)
        )
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def paired_comparison(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    left_name: str,
    right_name: str,
    repetitions: int,
    seed: int,
) -> list[dict[str, Any]]:
    left_by_id = {row["run_id"]: row for row in left}
    right_by_id = {row["run_id"]: row for row in right}
    if set(left_by_id) != set(right_by_id):
        missing_left = sorted(set(right_by_id) - set(left_by_id))
        missing_right = sorted(set(left_by_id) - set(right_by_id))
        raise ValueError(
            f"Unpaired reports: missing {left_name}={missing_left}, "
            f"missing {right_name}={missing_right}"
        )

    output: list[dict[str, Any]] = []
    for scope_index, (scope, scope_seed) in enumerate(
        (("seed0", 0), ("seed1", 1), ("all", None))
    ):
        paired: list[dict[str, Any]] = []
        left_only = 0
        right_only = 0
        for run_id in sorted(left_by_id):
            left_row = left_by_id[run_id]
            if scope_seed is not None and left_row["seed"] != scope_seed:
                continue
            right_row = right_by_id[run_id]
            paired.append({
                "taskid": left_row["taskid"],
                "difference": (
                    int(left_row["correct"]) - int(right_row["correct"])
                ),
            })
            left_only += int(left_row["correct"] and not right_row["correct"])
            right_only += int(right_row["correct"] and not left_row["correct"])
        low, high = _cluster_interval(
            paired, repetitions, seed + scope_index
        )
        output.append({
            "scope": scope,
            "left": left_name,
            "right": right_name,
            "left_accuracy": round(
                sum(left_by_id[row_id]["correct"] for row_id in left_by_id
                    if scope_seed is None
                    or left_by_id[row_id]["seed"] == scope_seed)
                / len(paired),
                6,
            ),
            "right_accuracy": round(
                sum(right_by_id[row_id]["correct"] for row_id in right_by_id
                    if scope_seed is None
                    or right_by_id[row_id]["seed"] == scope_seed)
                / len(paired),
                6,
            ),
            "left_minus_right": round(
                sum(row["difference"] for row in paired) / len(paired), 6
            ),
            "ci95_low": round(low, 6),
            "ci95_high": round(high, 6),
            "left_correct_right_wrong": left_only,
            "left_wrong_right_correct": right_only,
            "mcnemar_exact_p_unclustered": round(
                _exact_mcnemar_p(left_only, right_only), 8
            ),
            "n_reports": len(paired),
        })
    return output


def audit_protocol(
    conditions: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    reference = {row["run_id"]: row for row in conditions["full"]}
    mismatches: list[dict[str, Any]] = []
    comparisons = 0
    for condition_name in ("queries", "snippets"):
        current = {row["run_id"]: row for row in conditions[condition_name]}
        if set(current) != set(reference):
            raise ValueError(
                f"Protocol audit has unpaired {condition_name} reports"
            )
        for run_id, reference_row in reference.items():
            comparisons += 1
            row = current[run_id]
            fields = (
                "gt_userid",
                "candidate_userids",
                "shuffled_order",
                "shuffle_algorithm",
                "shuffle_seed",
            )
            differing = [
                field for field in fields
                if row.get(field) != reference_row.get(field)
            ]
            if differing:
                mismatches.append({
                    "condition": condition_name,
                    "run_id": run_id,
                    "fields": differing,
                })
    if mismatches:
        raise ValueError(
            f"Search-view protocol mismatch: {mismatches[:5]}"
        )
    return {
        "reference_reports": len(reference),
        "paired_view_comparisons": comparisons,
        "candidate_set_matches": comparisons,
        "candidate_order_matches": comparisons,
        "mismatches": 0,
        "passed": True,
    }


def analyze(
    full_dir: Path,
    queries_dir: Path,
    snippets_dir: Path,
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    conditions = {
        "full": load_search_matches(full_dir),
        "queries": load_search_matches(queries_dir),
        "snippets": load_search_matches(snippets_dir),
    }
    return {
        "schema_version": 2,
        "external_api_calls": 0,
        "population": {
            name: len(rows) for name, rows in conditions.items()
        },
        "protocol_audit": audit_protocol(conditions),
        "comparisons": (
            paired_comparison(
                conditions["queries"], conditions["full"],
                "queries", "full", repetitions, seed
            )
            + paired_comparison(
                conditions["snippets"], conditions["full"],
                "snippets", "full", repetitions, seed + 10
            )
            + paired_comparison(
                conditions["queries"], conditions["snippets"],
                "queries", "snippets", repetitions, seed + 20
            )
        ),
        "claim_boundary": (
            "Search views are post-hoc artifact decompositions, not "
            "generation-time causal interventions."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-dir", type=Path, default=DEFAULT_FULL)
    parser.add_argument("--queries-dir", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--snippets-dir", type=Path, default=DEFAULT_SNIPPETS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260803)
    args = parser.parse_args()
    result = analyze(
        args.full_dir, args.queries_dir, args.snippets_dir,
        args.bootstrap_repetitions, args.bootstrap_seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Search-view analysis → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
