"""Analyze full/actionable-only/identity-only attribution conditions.

Network-free. The analysis requires completed matcher outputs and pairs every
condition at task/persona/seed/stage grain using the frozen ablation subset.
"""

from __future__ import annotations

import argparse
import csv
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

from scripts.analyze_matches import (
    STAGES,
    _exact_mcnemar_p,
    _percentile,
    bootstrap_stage_rows,
    load_match_records,
    load_run_summaries,
)

DEFAULT_MANIFEST = ROOT / "manifest.json"
DEFAULT_FULL_MATCHES = ROOT / "runs" / "confirmatory" / "matches_sha256"
DEFAULT_ACTIONABLE_RUNS = ROOT / "runs" / "ablation" / "actionable_only"
DEFAULT_IDENTITY_RUNS = ROOT / "runs" / "ablation" / "identity_only"
DEFAULT_OUTPUT = ROOT / "runs" / "ablation" / "analysis"
USER_RE = re.compile(r"_(User\d+)_seed\d+$")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _userid(record: dict[str, Any]) -> str:
    userid = record.get("gt_userid")
    if userid:
        return str(userid)
    match = USER_RE.search(str(record["run_id"]))
    if match is None:
        raise ValueError(f"Cannot parse userid: {record['run_id']}")
    return match.group(1)


def pairing_key(record: dict[str, Any]) -> tuple[int, str, int, str]:
    return (
        int(record["taskid"]),
        _userid(record),
        int(record["seed"]),
        str(record["stage"]),
    )


def quality_summary(
    condition: str,
    run_dir: Path,
    expected_reports: int,
) -> dict[str, Any]:
    summaries = load_run_summaries(run_dir)
    rows = list(summaries.values())
    ledgers = [
        row.get("token_ledger", {})
        for row in rows
        if isinstance(row.get("token_ledger"), dict)
    ]
    return {
        "condition": condition,
        "expected_reports": expected_reports,
        "completed_reports": len(rows),
        "missing_reports": max(0, expected_reports - len(rows)),
        "schema_valid_reports": sum(
            row.get("schema_valid") is True for row in rows
        ),
        "success_criteria_met_reports": sum(
            row.get("success_criteria_met") is True for row in rows
        ),
        "completeness_issue_reports": sum(
            bool(row.get("completeness_errors")) for row in rows
        ),
        "execution_error_reports": sum(
            row.get("execution_error") is not None for row in rows
        ),
        "ledger_issue_reports": sum(
            bool(row.get("ledger_errors")) for row in rows
        ),
        "total_tokens": sum(
            int(ledger.get("total_tokens", 0) or 0) for ledger in ledgers
        ),
        "queries_attempted": sum(
            int(ledger.get("queries_attempted", 0) or 0)
            for ledger in ledgers
        ),
        "queries_successful": sum(
            int(ledger.get("queries_successful", 0) or 0)
            for ledger in ledgers
        ),
    }


def generation_quality_gate(
    actionable_run_dir: Path,
    identity_run_dir: Path,
    expected_reports: int,
) -> dict[str, Any]:
    quality = [
        quality_summary(
            "actionable_only", actionable_run_dir, expected_reports
        ),
        quality_summary(
            "identity_only", identity_run_dir, expected_reports
        ),
    ]
    checks: list[dict[str, Any]] = []
    for row in quality:
        passed = (
            row["completed_reports"] == expected_reports
            and row["schema_valid_reports"] == expected_reports
            and row["success_criteria_met_reports"] == expected_reports
            and row["completeness_issue_reports"] == 0
            and row["execution_error_reports"] == 0
            and row["ledger_issue_reports"] == 0
        )
        checks.append({
            "condition": row["condition"],
            "passed": passed,
            "reasons": [
                label
                for label, failed in [
                    (
                        "incomplete report count",
                        row["completed_reports"] != expected_reports,
                    ),
                    (
                        "schema-invalid report",
                        row["schema_valid_reports"] != expected_reports,
                    ),
                    (
                        "success criteria not met",
                        row["success_criteria_met_reports"]
                        != expected_reports,
                    ),
                    (
                        "completeness issue",
                        row["completeness_issue_reports"] != 0,
                    ),
                    (
                        "execution error",
                        row["execution_error_reports"] != 0,
                    ),
                    (
                        "ledger issue",
                        row["ledger_issue_reports"] != 0,
                    ),
                ]
                if failed
            ],
        })
    return {
        "schema_version": 1,
        "external_api_calls": 0,
        "expected_reports_per_condition": expected_reports,
        "passed": all(check["passed"] for check in checks),
        "quality": quality,
        "checks": checks,
    }


def comparability(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    left_name: str,
    right_name: str,
) -> dict[str, Any]:
    left_map = {pairing_key(row): row for row in left}
    right_map = {pairing_key(row): row for row in right}
    shared = sorted(set(left_map) & set(right_map))
    order_matches = sum(
        left_map[key]["shuffled_order"] == right_map[key]["shuffled_order"]
        for key in shared
    )
    candidate_set_matches = sum(
        set(left_map[key]["candidate_userids"])
        == set(right_map[key]["candidate_userids"])
        for key in shared
    )
    return {
        "left": left_name,
        "right": right_name,
        "left_pairs": len(left_map),
        "right_pairs": len(right_map),
        "shared_pairs": len(shared),
        "left_only_pairs": len(set(left_map) - set(right_map)),
        "right_only_pairs": len(set(right_map) - set(left_map)),
        "candidate_set_matches": candidate_set_matches,
        "candidate_order_matches": order_matches,
        "directly_comparable": (
            len(left_map) == len(right_map) == len(shared)
            and candidate_set_matches == len(shared)
            and order_matches == len(shared)
        ),
    }


def _paired_interval(
    rows: list[dict[str, Any]],
    repetitions: int,
    seed: int,
) -> tuple[float, float]:
    by_task: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[int(row["taskid"])].append(row)
    taskids = sorted(by_task)
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(repetitions):
        sample: list[dict[str, Any]] = []
        for taskid in rng.choices(taskids, k=len(taskids)):
            sample.extend(by_task[taskid])
        values.append(
            sum(item["difference"] for item in sample) / len(sample)
        )
    return _percentile(values, 0.025), _percentile(values, 0.975)


def paired_condition_rows(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    left_name: str,
    right_name: str,
    repetitions: int,
    seed: int,
) -> list[dict[str, Any]]:
    left_map = {pairing_key(row): row for row in left}
    right_map = {pairing_key(row): row for row in right}
    if set(left_map) != set(right_map):
        raise ValueError(
            f"Unpaired conditions {left_name}/{right_name}: "
            f"{len(set(left_map) - set(right_map))} left-only, "
            f"{len(set(right_map) - set(left_map))} right-only"
        )
    rows: list[dict[str, Any]] = []
    for index, stage in enumerate(STAGES):
        paired: list[dict[str, Any]] = []
        left_only = 0
        right_only = 0
        for key in sorted(left_map):
            if key[3] != stage:
                continue
            first = left_map[key]
            second = right_map[key]
            paired.append({
                "taskid": key[0],
                "difference": (
                    int(first["correct"]) - int(second["correct"])
                ),
            })
            left_only += int(first["correct"] and not second["correct"])
            right_only += int(not first["correct"] and second["correct"])
        low, high = _paired_interval(
            paired, repetitions, seed + index
        )
        rows.append({
            "left": left_name,
            "right": right_name,
            "stage": stage,
            "left_accuracy": round(
                sum(int(left_map[key]["correct"]) for key in left_map
                    if key[3] == stage) / len(paired),
                6,
            ),
            "right_accuracy": round(
                sum(int(right_map[key]["correct"]) for key in right_map
                    if key[3] == stage) / len(paired),
                6,
            ),
            "left_minus_right": round(
                sum(item["difference"] for item in paired) / len(paired), 6
            ),
            "ci95_low": round(low, 6),
            "ci95_high": round(high, 6),
            "left_correct_right_wrong": left_only,
            "left_wrong_right_correct": right_only,
            "mcnemar_exact_p_unclustered": round(
                _exact_mcnemar_p(left_only, right_only), 8
            ),
            "n_paired_reports": len(paired),
            "n_tasks": len({item["taskid"] for item in paired}),
        })
    return rows


def analyze(
    manifest: dict[str, Any],
    full_match_dir: Path,
    actionable_run_dir: Path,
    identity_run_dir: Path,
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    taskids = set(manifest["pdr_bench"]["ablation_subset"]["taskids"])
    expected_per_condition = int(
        manifest["pdr_bench"]["ablation_subset"]["generation_conditions"][
            "actionable_only"
        ]["reports"]
    )
    actionable_matches = load_match_records(
        actionable_run_dir / "matches"
    )
    identity_matches = load_match_records(identity_run_dir / "matches")
    observed_seeds = sorted({
        int(row["seed"]) for row in actionable_matches + identity_matches
    })
    expected_reports = (
        expected_per_condition
        if observed_seeds == [0, 1]
        else expected_per_condition // 2
    )
    full_matches = [
        row for row in load_match_records(full_match_dir)
        if int(row["taskid"]) in taskids
        and int(row["seed"]) in observed_seeds
    ]
    conditions = {
        "full": full_matches,
        "actionable_only": actionable_matches,
        "identity_only": identity_matches,
    }
    expected_pairs = expected_reports * len(STAGES)
    for name, rows in conditions.items():
        if len(rows) != expected_pairs:
            raise ValueError(
                f"{name}: expected {expected_pairs} match rows, got {len(rows)}"
            )
    checks = [
        comparability(
            conditions["actionable_only"], conditions["full"],
            "actionable_only", "full",
        ),
        comparability(
            conditions["identity_only"], conditions["full"],
            "identity_only", "full",
        ),
        comparability(
            conditions["actionable_only"], conditions["identity_only"],
            "actionable_only", "identity_only",
        ),
    ]
    if not all(check["directly_comparable"] for check in checks):
        raise ValueError(f"Condition comparability failed: {checks}")
    stage_rows: list[dict[str, Any]] = []
    for index, (name, rows) in enumerate(conditions.items()):
        stage_rows.extend({
            "condition": name,
            **row,
        } for row in bootstrap_stage_rows(
            rows, repetitions, seed + index * 10
        ))
    paired_rows = (
        paired_condition_rows(
            conditions["actionable_only"], conditions["full"],
            "actionable_only", "full", repetitions, seed + 100,
        )
        + paired_condition_rows(
            conditions["identity_only"], conditions["full"],
            "identity_only", "full", repetitions, seed + 200,
        )
        + paired_condition_rows(
            conditions["actionable_only"], conditions["identity_only"],
            "actionable_only", "identity_only", repetitions, seed + 300,
        )
    )
    return {
        "schema_version": 1,
        "external_api_calls": 0,
        "status": (
            "seed0_gate" if observed_seeds == [0] else "two_seed_final"
        ),
        "population": {
            "taskids": sorted(taskids),
            "seeds": observed_seeds,
            "reports_per_condition": expected_reports,
            "run_stage_pairs_per_condition": expected_pairs,
        },
        "quality": [
            quality_summary(
                "actionable_only", actionable_run_dir, expected_reports
            ),
            quality_summary(
                "identity_only", identity_run_dir, expected_reports
            ),
        ],
        "comparability": checks,
        "condition_stage_accuracy": stage_rows,
        "paired_condition_differences": paired_rows,
        "claim_boundary": (
            "Seed-0 output is a technical gate, not the final confirmatory "
            "condition effect. Leaf-key profiles do not resolve within-leaf "
            "semantic ambiguity."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--full-match-dir", type=Path, default=DEFAULT_FULL_MATCHES
    )
    parser.add_argument(
        "--actionable-run-dir", type=Path, default=DEFAULT_ACTIONABLE_RUNS
    )
    parser.add_argument(
        "--identity-run-dir", type=Path, default=DEFAULT_IDENTITY_RUNS
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--quality-only",
        action="store_true",
        help="Check completed generation summaries without matcher outputs.",
    )
    parser.add_argument(
        "--seed-count",
        type=int,
        choices=(1, 2),
        default=1,
        help="Expected ablation generation seeds for --quality-only.",
    )
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260803)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.quality_only:
        reports_for_two_seeds = int(
            manifest["pdr_bench"]["ablation_subset"][
                "generation_conditions"
            ]["actionable_only"]["reports"]
        )
        result = generation_quality_gate(
            args.actionable_run_dir,
            args.identity_run_dir,
            reports_for_two_seeds * args.seed_count // 2,
        )
        gate_path = args.output_dir / "generation_quality_gate.json"
        gate_path.write_text(
            json.dumps(
                result, indent=2, ensure_ascii=False, sort_keys=True
            ),
            encoding="utf-8",
        )
        print(
            f"Generation quality gate ({'PASS' if result['passed'] else 'WAIT/FAIL'})"
            f" → {gate_path}"
        )
        return 0 if result["passed"] else 1
    result = analyze(
        manifest,
        args.full_match_dir,
        args.actionable_run_dir,
        args.identity_run_dir,
        args.bootstrap_repetitions,
        args.bootstrap_seed,
    )
    summary_path = args.output_dir / "generation_ablation_summary.json"
    summary_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    _write_csv(
        args.output_dir / "condition_stage_accuracy.csv",
        result["condition_stage_accuracy"],
    )
    _write_csv(
        args.output_dir / "paired_condition_differences.csv",
        result["paired_condition_differences"],
    )
    print(f"Generation-ablation analysis → {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
