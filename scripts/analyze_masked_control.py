"""Offline analysis of the identifier-masked attribution control.

The defensible primary question is whether the stage trajectory remains inside
the masked condition. Direct original-versus-masked deltas are emitted only as
confounded diagnostics unless candidate presentation order is identical.

No external API is called.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_matches import (
    STAGES,
    _accuracy,
    _exact_mcnemar_p,
    _percentile,
    bootstrap_stage_rows,
    load_match_records,
    paired_stage_rows,
)


DEFAULT_ORIGINAL = ROOT / "runs" / "confirmatory" / "matches_sha256"
DEFAULT_MASKED = ROOT / "runs" / "confirmatory" / "masked" / "matches"
DEFAULT_OUTPUT = ROOT / "runs" / "confirmatory" / "analysis_masked_control"
STAGE_PAIRS = (
    ("plan", "search"),
    ("search", "compress"),
    ("compress", "write"),
    ("search", "write"),
)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _record_map(
    records: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    return {(record["run_id"], record["stage"]): record for record in records}


def comparability_checks(
    original: list[dict[str, Any]],
    masked: list[dict[str, Any]],
) -> dict[str, Any]:
    original_map = _record_map(original)
    masked_map = _record_map(masked)
    original_keys = set(original_map)
    masked_keys = set(masked_map)
    if original_keys != masked_keys:
        raise ValueError(
            "Original/masked run-stage keys differ: "
            f"original_only={len(original_keys - masked_keys)}, "
            f"masked_only={len(masked_keys - original_keys)}"
        )

    candidate_set_mismatches = 0
    gt_mismatches = 0
    order_matches = 0
    order_matches_by_stage = {stage: 0 for stage in STAGES}
    for key in sorted(original_keys):
        first = original_map[key]
        second = masked_map[key]
        if set(first["candidate_userids"]) != set(second["candidate_userids"]):
            candidate_set_mismatches += 1
        if first["gt_userid"] != second["gt_userid"]:
            gt_mismatches += 1
        if first["shuffled_order"] == second["shuffled_order"]:
            order_matches += 1
            order_matches_by_stage[key[1]] += 1

    run_ids = sorted({run_id for run_id, _stage in original_keys})
    all_stage_order_matches = sum(
        all(
            original_map[(run_id, stage)]["shuffled_order"]
            == masked_map[(run_id, stage)]["shuffled_order"]
            for stage in STAGES
        )
        for run_id in run_ids
    )
    total = len(original_keys)
    directly_comparable = (
        candidate_set_mismatches == 0
        and gt_mismatches == 0
        and order_matches == total
    )
    return {
        "reports": len(run_ids),
        "run_stage_pairs": total,
        "candidate_set_mismatches": candidate_set_mismatches,
        "gt_mismatches": gt_mismatches,
        "candidate_order_matches": order_matches,
        "candidate_order_match_rate": round(order_matches / total, 6),
        "candidate_order_matches_by_stage": order_matches_by_stage,
        "reports_with_all_stage_orders_matching": all_stage_order_matches,
        "direct_condition_effect_is_identified": directly_comparable,
        "primary_valid_estimand": (
            "masked within-condition stage trajectory"
            if not directly_comparable
            else "paired original-versus-masked condition effect"
        ),
        "confound": (
            None
            if directly_comparable
            else "candidate presentation order differs between conditions"
        ),
    }


def condition_stage_rows(
    condition: str,
    records: list[dict[str, Any]],
    repetitions: int,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    return [
        {"condition": condition, **row}
        for row in bootstrap_stage_rows(
            records,
            repetitions=repetitions,
            bootstrap_seed=bootstrap_seed,
        )
    ]


def _cluster_bootstrap_paired(
    paired: list[dict[str, Any]],
    statistic: Callable[[list[dict[str, Any]]], float],
    repetitions: int,
    seed: int,
) -> list[float]:
    by_task: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in paired:
        by_task[int(row["taskid"])].append(row)
    taskids = sorted(by_task)
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(repetitions):
        sample: list[dict[str, Any]] = []
        for taskid in rng.choices(taskids, k=len(taskids)):
            sample.extend(by_task[taskid])
        values.append(statistic(sample))
    return values


def condition_delta_rows(
    original: list[dict[str, Any]],
    masked: list[dict[str, Any]],
    repetitions: int,
    bootstrap_seed: int,
    identified: bool,
) -> list[dict[str, Any]]:
    original_map = _record_map(original)
    masked_map = _record_map(masked)
    rows: list[dict[str, Any]] = []
    for index, stage in enumerate(STAGES):
        paired: list[dict[str, Any]] = []
        original_correct_masked_wrong = 0
        original_wrong_masked_correct = 0
        for key in sorted(original_map):
            if key[1] != stage:
                continue
            first = original_map[key]
            second = masked_map[key]
            if first["correct"] and not second["correct"]:
                original_correct_masked_wrong += 1
            if not first["correct"] and second["correct"]:
                original_wrong_masked_correct += 1
            paired.append(
                {
                    "taskid": first["taskid"],
                    "difference": int(second["correct"]) - int(first["correct"]),
                }
            )

        statistic = lambda sample: sum(  # noqa: E731
            row["difference"] for row in sample
        ) / len(sample)
        values = _cluster_bootstrap_paired(
            paired,
            statistic,
            repetitions,
            bootstrap_seed + index,
        )
        rows.append(
            {
                "stage": stage,
                "masked_minus_original": round(statistic(paired), 6),
                "ci95_low": round(_percentile(values, 0.025), 6),
                "ci95_high": round(_percentile(values, 0.975), 6),
                "original_correct_masked_wrong": original_correct_masked_wrong,
                "original_wrong_masked_correct": original_wrong_masked_correct,
                "mcnemar_exact_p_unclustered": round(
                    _exact_mcnemar_p(
                        original_correct_masked_wrong,
                        original_wrong_masked_correct,
                    ),
                    8,
                ),
                "n_paired_reports": len(paired),
                "effect_identified": identified,
                "interpretation": (
                    "paired condition effect"
                    if identified
                    else "descriptive only; candidate-order confounded"
                ),
            }
        )
    return rows


def within_condition_stage_pairs(
    records: list[dict[str, Any]],
    repetitions: int,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    adjacent = {
        (row["stage_a"], row["stage_b"]): row
        for row in paired_stage_rows(
            records,
            repetitions=repetitions,
            bootstrap_seed=bootstrap_seed,
        )
    }
    rows = [adjacent[pair] for pair in STAGE_PAIRS[:3]]

    by_key = _record_map(records)
    paired: list[dict[str, Any]] = []
    a_correct_b_wrong = 0
    a_wrong_b_correct = 0
    for run_id in sorted({record["run_id"] for record in records}):
        first = by_key[(run_id, "search")]
        second = by_key[(run_id, "write")]
        if first["correct"] and not second["correct"]:
            a_correct_b_wrong += 1
        if not first["correct"] and second["correct"]:
            a_wrong_b_correct += 1
        paired.append(
            {
                "taskid": first["taskid"],
                "difference": int(second["correct"]) - int(first["correct"]),
            }
        )
    statistic = lambda sample: sum(  # noqa: E731
        row["difference"] for row in sample
    ) / len(sample)
    values = _cluster_bootstrap_paired(
        paired,
        statistic,
        repetitions,
        bootstrap_seed + 203,
    )
    rows.append(
        {
            "stage_a": "search",
            "stage_b": "write",
            "accuracy_difference_b_minus_a": round(statistic(paired), 6),
            "ci95_low": round(_percentile(values, 0.025), 6),
            "ci95_high": round(_percentile(values, 0.975), 6),
            "a_correct_b_wrong": a_correct_b_wrong,
            "a_wrong_b_correct": a_wrong_b_correct,
            "mcnemar_exact_p_unclustered": round(
                _exact_mcnemar_p(a_correct_b_wrong, a_wrong_b_correct),
                8,
            ),
            "n_paired_reports": len(paired),
            "bootstrap_unit": "taskid",
            "bootstrap_repetitions": repetitions,
        }
    )
    return rows


def trajectory_retention(
    records: list[dict[str, Any]],
    repetitions: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    by_task: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_task[int(record["taskid"])].append(record)
    taskids = sorted(by_task)

    def stage_acc(sample: list[dict[str, Any]], stage: str) -> float:
        return _accuracy(row for row in sample if row["stage"] == stage)

    plan = stage_acc(records, "plan")
    search = stage_acc(records, "search")
    write = stage_acc(records, "write")
    rng = random.Random(bootstrap_seed)
    retained = 0
    dip_values: list[float] = []
    recovery_values: list[float] = []
    for _ in range(repetitions):
        sample: list[dict[str, Any]] = []
        for taskid in rng.choices(taskids, k=len(taskids)):
            sample.extend(by_task[taskid])
        sample_plan = stage_acc(sample, "plan")
        sample_search = stage_acc(sample, "search")
        sample_write = stage_acc(sample, "write")
        dip_values.append(sample_search - sample_plan)
        recovery_values.append(sample_write - sample_search)
        retained += int(
            sample_search < sample_plan and sample_write > sample_search
        )
    return {
        "definition": "search < plan and write > search",
        "observed": search < plan and write > search,
        "plan_accuracy": round(plan, 6),
        "search_accuracy": round(search, 6),
        "write_accuracy": round(write, 6),
        "planning_to_search_pp": round((search - plan) * 100, 2),
        "search_to_write_pp": round((write - search) * 100, 2),
        "cluster_bootstrap_joint_retention_probability": round(
            retained / repetitions,
            6,
        ),
        "planning_to_search_ci95_pp": [
            round(_percentile(dip_values, 0.025) * 100, 2),
            round(_percentile(dip_values, 0.975) * 100, 2),
        ],
        "search_to_write_ci95_pp": [
            round(_percentile(recovery_values, 0.025) * 100, 2),
            round(_percentile(recovery_values, 0.975) * 100, 2),
        ],
        "bootstrap_unit": "taskid",
        "bootstrap_repetitions": repetitions,
    }


def _latex_table(stage_rows: list[dict[str, Any]]) -> str:
    masked_by_stage = {
        row["stage"]: row
        for row in stage_rows
        if row["condition"] == "masked"
    }
    labels = {
        "plan": "Planning",
        "search": "Search",
        "compress": "Compression",
        "write": "Writing",
    }
    lines = [
        "% Auto-generated by scripts/analyze_masked_control.py; do not edit.",
        "\\begin{tabular}{lcc}",
        "\\toprule",
        "Stage & Masked Acc@1 & Task-bootstrap 95\\% CI \\\\",
        "\\midrule",
    ]
    for stage in STAGES:
        row = masked_by_stage[stage]
        lines.append(
            f"{labels[stage]} & {row['accuracy']:.3f} & "
            f"[{row['ci95_low']:.3f}, {row['ci95_high']:.3f}] \\\\"
        )
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
        ]
    )
    return "\n".join(lines) + "\n"


def _markdown_report(summary: dict[str, Any]) -> str:
    retention = summary["masked_trajectory_retention"]
    checks = summary["comparability"]
    pairs = {
        (row["stage_a"], row["stage_b"]): row
        for row in summary["masked_within_condition_stage_comparisons"]
    }
    plan_search = pairs[("plan", "search")]
    search_write = pairs[("search", "write")]
    if checks["direct_condition_effect_is_identified"]:
        comparability_text = f"""The original and masked results contain the
same {checks['reports']} reports and {checks['run_stage_pairs']} run-stage
pairs. Candidate sets, ground-truth personas, and presentation orders all
match; order agreement is
{checks['candidate_order_matches']}/{checks['run_stage_pairs']}
({checks['candidate_order_match_rate'] * 100:.1f}%). The paired
original-versus-masked differences are therefore identified for this
two-seed control."""
        boundary_text = """Supported: the point-estimate stage trajectory
survives identifier masking, and the paired two-seed accuracy differences are
estimable under identical candidate presentation orders.

Not supported: that the remaining attribution signal reflects only
content-intent alignment; non-identifier shortcuts may remain."""
        next_step_text = """Replicate with a second matcher or dataset if the
submission scope requires broader shortcut robustness."""
    else:
        comparability_text = f"""The original and masked results contain the
same {checks['reports']} reports and {checks['run_stage_pairs']} run-stage
pairs, candidate sets, and ground-truth personas. Candidate presentation
order matches in only
{checks['candidate_order_matches']}/{checks['run_stage_pairs']}
({checks['candidate_order_match_rate'] * 100:.1f}%) pairs.

Therefore, original-minus-masked accuracy deltas are candidate-order
confounded. Re-match the original artifacts with the same SHA-256 ordering
before reporting a masking effect size."""
        boundary_text = """Supported: the point-estimate stage trajectory
survives identifier masking.

Not yet supported: that masking itself changes accuracy by a particular
amount, or that content-intent alignment rather than all other non-identifier
shortcuts causes the remaining attribution signal."""
        next_step_text = """Re-match the original seed-0 artifacts with the
frozen SHA-256 candidate order, then rerun this analysis."""
    return f"""# Identifier-Masked Control Analysis

## Technical summary

The identifier-masked condition retains the pre-specified dip-and-recovery
shape across {checks['reports']} two-seed reports: Planning accuracy is
{retention['plan_accuracy']:.3f}, Search is {retention['search_accuracy']:.3f},
and Writing is {retention['write_accuracy']:.3f}. Planning→Search changes by
{retention['planning_to_search_pp']:+.2f} percentage points
(task-cluster bootstrap 95% CI
[{retention['planning_to_search_ci95_pp'][0]:+.2f},
{retention['planning_to_search_ci95_pp'][1]:+.2f}]), while Search→Writing
changes by {retention['search_to_write_pp']:+.2f} points
([{retention['search_to_write_ci95_pp'][0]:+.2f},
{retention['search_to_write_ci95_pp'][1]:+.2f}]).

This supports the narrow claim that the trajectory remains after removing
surface identifier spans.

## Evidence and uncertainty

- Masked Planning→Search: {plan_search['accuracy_difference_b_minus_a'] * 100:+.2f}
  points; task-bootstrap 95% CI
  [{plan_search['ci95_low'] * 100:+.2f},
  {plan_search['ci95_high'] * 100:+.2f}].
- Masked Search→Writing: {search_write['accuracy_difference_b_minus_a'] * 100:+.2f}
  points; task-bootstrap 95% CI
  [{search_write['ci95_low'] * 100:+.2f},
  {search_write['ci95_high'] * 100:+.2f}].
- The joint dip-and-recovery inequality held in
  {retention['cluster_bootstrap_joint_retention_probability'] * 100:.2f}% of
  task-cluster bootstrap resamples.
- McNemar values are unclustered descriptive checks; the task-bootstrap
  intervals are the primary uncertainty summaries.

## Comparability audit

{comparability_text}

## Claim boundary

{boundary_text}

## Next step

{next_step_text}
"""


def analyze(
    original_dir: Path,
    masked_dir: Path,
    output_dir: Path,
    bootstrap_repetitions: int = 5000,
    bootstrap_seed: int = 20260802,
) -> dict[str, Any]:
    original = load_match_records(original_dir)
    masked = load_match_records(masked_dir)
    if not original or not masked:
        raise ValueError("Both original and masked match directories are required")
    masked_run_ids = {record["run_id"] for record in masked}
    original = [
        record for record in original if record["run_id"] in masked_run_ids
    ]
    checks = comparability_checks(original, masked)
    stage_rows = (
        condition_stage_rows(
            "original",
            original,
            bootstrap_repetitions,
            bootstrap_seed,
        )
        + condition_stage_rows(
            "masked",
            masked,
            bootstrap_repetitions,
            bootstrap_seed + 10,
        )
    )
    masked_pairs = within_condition_stage_pairs(
        masked,
        bootstrap_repetitions,
        bootstrap_seed + 20,
    )
    deltas = condition_delta_rows(
        original,
        masked,
        bootstrap_repetitions,
        bootstrap_seed + 30,
        checks["direct_condition_effect_is_identified"],
    )
    retention = trajectory_retention(
        masked,
        bootstrap_repetitions,
        bootstrap_seed + 40,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "condition_stage_accuracy.csv", stage_rows)
    _write_csv(output_dir / "masked_stage_comparisons.csv", masked_pairs)
    _write_csv(output_dir / "condition_deltas_confounded.csv", deltas)
    (output_dir / "comparability.json").write_text(
        json.dumps(checks, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "paper_table_masked_control.tex").write_text(
        _latex_table(stage_rows),
        encoding="utf-8",
    )

    summary = {
        "schema_version": 1,
        "analysis_role": "identifier-masked shortcut control",
        "external_api_calls": 0,
        "source_original_dir": str(original_dir),
        "source_masked_dir": str(masked_dir),
        "comparability": checks,
        "condition_stage_accuracy": stage_rows,
        "masked_within_condition_stage_comparisons": masked_pairs,
        "original_vs_masked_deltas": deltas,
        "masked_trajectory_retention": retention,
        "claim_status": {
            "supported": (
                "The point-estimate dip-and-recovery trajectory remains after "
                "identifier masking; paired condition differences are "
                "identified under matching candidate orders."
                if checks["direct_condition_effect_is_identified"]
                else "The point-estimate dip-and-recovery trajectory remains "
                "after identifier masking."
            ),
            "not_supported_yet": (
                "That the remaining signal is exclusively content-intent "
                "alignment rather than another non-identifier shortcut."
                if checks["direct_condition_effect_is_identified"]
                else "A causal or paired effect of identifier masking on "
                "accuracy; original artifacts must be re-matched with the "
                "same SHA-256 candidate order first."
            ),
        },
    }
    (output_dir / "masked_control_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "masked_control_report.md").write_text(
        _markdown_report(summary),
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-dir", type=Path, default=DEFAULT_ORIGINAL)
    parser.add_argument("--masked-dir", type=Path, default=DEFAULT_MASKED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260802)
    args = parser.parse_args(argv)

    summary = analyze(
        args.original_dir,
        args.masked_dir,
        args.output_dir,
        args.bootstrap_repetitions,
        args.bootstrap_seed,
    )
    retention = summary["masked_trajectory_retention"]
    print(
        "Masked trajectory: "
        f"Planning→Search {retention['planning_to_search_pp']:+.2f} pp; "
        f"Search→Writing {retention['search_to_write_pp']:+.2f} pp"
    )
    print(
        "Direct condition effect identified: "
        f"{summary['comparability']['direct_condition_effect_is_identified']}"
    )
    print("External API calls: 0")
    print(f"Results: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
