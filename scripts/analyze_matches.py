"""Network-free statistical analysis for stage-wise persona matches.

The script consumes existing ``*_match.json`` files and per-run generation
summaries. It never calls an external API.

Usage:
    python scripts/analyze_matches.py \
      --match-dir runs/confirmatory/matches_sha256 \
      --run-dir runs/confirmatory \
      --output-dir runs/confirmatory/analysis_sha256
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

STAGES = ("plan", "search", "compress", "write")
ADJACENT_STAGE_PAIRS = (
    ("plan", "search"),
    ("search", "compress"),
    ("compress", "write"),
)
RUN_ID_RE = re.compile(r"_task(?P<taskid>\d+)_.*_seed(?P<seed>\d+)$")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _parse_run_id(run_id: str) -> tuple[int, int]:
    match = RUN_ID_RE.search(run_id)
    if not match:
        raise ValueError(f"Cannot parse task/seed from run_id: {run_id}")
    return int(match.group("taskid")), int(match.group("seed"))


def load_match_records(match_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(match_dir.glob("*_match.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise ValueError(f"Expected list in {path}")
        for record in value:
            if not isinstance(record, dict):
                raise ValueError(f"Expected object records in {path}")
            run_id = str(record.get("run_id", ""))
            stage = str(record.get("stage", ""))
            if stage not in STAGES:
                raise ValueError(f"Unknown stage {stage!r} in {path}")
            taskid, seed = _parse_run_id(run_id)
            normalized = dict(record)
            normalized["taskid"] = taskid
            normalized["seed"] = seed
            normalized["correct"] = bool(record.get("correct"))
            records.append(normalized)

    seen = Counter((record["run_id"], record["stage"]) for record in records)
    duplicates = [key for key, count in seen.items() if count != 1]
    if duplicates:
        raise ValueError(f"Duplicate match records: {duplicates[:5]}")
    return records


def load_run_summaries(run_dir: Path) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for path in sorted(run_dir.glob("*_summary.json")):
        if path.name.startswith("batch_"):
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not value.get("run_id"):
            continue
        summaries[str(value["run_id"])] = value
    return summaries


def _accuracy(records: Iterable[dict[str, Any]]) -> float:
    values = [int(record["correct"]) for record in records]
    return sum(values) / len(values) if values else float("nan")


def stage_accuracy_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seeds = sorted({int(record["seed"]) for record in records})
    rows: list[dict[str, Any]] = []
    for seed_label, predicate in [
        *((str(seed), lambda record, seed=seed: record["seed"] == seed) for seed in seeds),
        ("all", lambda record: True),
    ]:
        selected = [record for record in records if predicate(record)]
        for stage in STAGES:
            stage_records = [
                record for record in selected if record["stage"] == stage
            ]
            rows.append(
                {
                    "seed": seed_label,
                    "stage": stage,
                    "correct": sum(
                        int(record["correct"]) for record in stage_records
                    ),
                    "n": len(stage_records),
                    "accuracy": round(_accuracy(stage_records), 6),
                }
            )
    return rows


def seed_variance_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seeds = sorted({int(record["seed"]) for record in records})
    rows: list[dict[str, Any]] = []
    for stage in STAGES:
        accuracies = [
            _accuracy(
                record
                for record in records
                if record["stage"] == stage and record["seed"] == seed
            )
            for seed in seeds
        ]
        mean = sum(accuracies) / len(accuracies)
        population_sd = (
            math.sqrt(
                sum((value - mean) ** 2 for value in accuracies)
                / len(accuracies)
            )
            if len(accuracies) >= 2 else None
        )
        rows.append(
            {
                "stage": stage,
                "seeds": ",".join(str(seed) for seed in seeds),
                "n_seeds": len(seeds),
                "mean_accuracy": round(mean, 6),
                "population_sd_across_seeds": (
                    round(population_sd, 6)
                    if population_sd is not None else None
                ),
                "min_accuracy": round(min(accuracies), 6),
                "max_accuracy": round(max(accuracies), 6),
            }
        )
    return rows


def _cluster_bootstrap_values(
    records: list[dict[str, Any]],
    statistic: Callable[[list[dict[str, Any]]], float],
    repetitions: int,
    rng: random.Random,
) -> list[float]:
    by_task: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_task[int(record["taskid"])].append(record)
    taskids = sorted(by_task)
    if not taskids:
        return []

    values: list[float] = []
    for _ in range(repetitions):
        sampled: list[dict[str, Any]] = []
        for taskid in rng.choices(taskids, k=len(taskids)):
            sampled.extend(by_task[taskid])
        value = statistic(sampled)
        if not math.isnan(value):
            values.append(value)
    return values


def bootstrap_stage_rows(
    records: list[dict[str, Any]],
    repetitions: int,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, stage in enumerate(STAGES):
        stage_records = [
            record for record in records if record["stage"] == stage
        ]
        values = _cluster_bootstrap_values(
            stage_records,
            _accuracy,
            repetitions,
            random.Random(bootstrap_seed + index),
        )
        rows.append(
            {
                "stage": stage,
                "accuracy": round(_accuracy(stage_records), 6),
                "ci95_low": round(_percentile(values, 0.025), 6),
                "ci95_high": round(_percentile(values, 0.975), 6),
                "bootstrap_unit": "taskid",
                "bootstrap_repetitions": repetitions,
                "bootstrap_seed": bootstrap_seed + index,
                "n_reports": len(stage_records),
                "n_tasks": len(
                    {record["taskid"] for record in stage_records}
                ),
            }
        )
    return rows


def _exact_mcnemar_p(discordant_a: int, discordant_b: int) -> float:
    total = discordant_a + discordant_b
    if total == 0:
        return 1.0
    tail_end = min(discordant_a, discordant_b)
    probability = sum(
        math.comb(total, index) for index in range(tail_end + 1)
    ) / (2 ** total)
    return min(1.0, 2 * probability)


def paired_stage_rows(
    records: list[dict[str, Any]],
    repetitions: int,
    bootstrap_seed: int,
) -> list[dict[str, Any]]:
    by_run_stage = {
        (record["run_id"], record["stage"]): record
        for record in records
    }
    run_ids = sorted({record["run_id"] for record in records})
    rows: list[dict[str, Any]] = []

    for index, (stage_a, stage_b) in enumerate(ADJACENT_STAGE_PAIRS):
        paired: list[dict[str, Any]] = []
        a_correct_b_wrong = 0
        a_wrong_b_correct = 0
        for run_id in run_ids:
            first = by_run_stage.get((run_id, stage_a))
            second = by_run_stage.get((run_id, stage_b))
            if first is None or second is None:
                continue
            if first["correct"] and not second["correct"]:
                a_correct_b_wrong += 1
            if not first["correct"] and second["correct"]:
                a_wrong_b_correct += 1
            paired.append(
                {
                    "run_id": run_id,
                    "taskid": first["taskid"],
                    "difference": int(second["correct"]) - int(first["correct"]),
                }
            )

        def mean_difference(sample: list[dict[str, Any]]) -> float:
            return (
                sum(item["difference"] for item in sample) / len(sample)
                if sample else float("nan")
            )

        values = _cluster_bootstrap_values(
            paired,
            mean_difference,
            repetitions,
            random.Random(bootstrap_seed + 100 + index),
        )
        difference = mean_difference(paired)
        rows.append(
            {
                "stage_a": stage_a,
                "stage_b": stage_b,
                "accuracy_difference_b_minus_a": round(difference, 6),
                "ci95_low": round(_percentile(values, 0.025), 6),
                "ci95_high": round(_percentile(values, 0.975), 6),
                "a_correct_b_wrong": a_correct_b_wrong,
                "a_wrong_b_correct": a_wrong_b_correct,
                "mcnemar_exact_p_unclustered": round(
                    _exact_mcnemar_p(
                        a_correct_b_wrong,
                        a_wrong_b_correct,
                    ),
                    8,
                ),
                "n_paired_reports": len(paired),
                "bootstrap_unit": "taskid",
                "bootstrap_repetitions": repetitions,
            }
        )
    return rows


def run_distribution_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_run[record["run_id"]].append(record)
    counts = Counter(
        sum(int(record["correct"]) for record in run_records)
        for run_records in by_run.values()
    )
    total = len(by_run)
    return [
        {
            "correct_stages": correct_stages,
            "reports": counts.get(correct_stages, 0),
            "fraction": round(
                counts.get(correct_stages, 0) / total if total else float("nan"),
                6,
            ),
        }
        for correct_stages in range(len(STAGES) + 1)
    ]


def confusion_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors = [
        record for record in records
        if not record["correct"]
    ]
    counts = Counter(
        (
            str(record.get("gt_userid", "")),
            str(record.get("predicted_userid", "")),
            str(record["stage"]),
        )
        for record in errors
    )
    return [
        {
            "gt_userid": gt_userid,
            "predicted_userid": predicted_userid,
            "stage": stage,
            "errors": count,
        }
        for (gt_userid, predicted_userid, stage), count
        in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def sensitivity_rows(
    records: list[dict[str, Any]],
    summaries: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    policies: list[tuple[str, Callable[[dict[str, Any]], bool]]] = [
        ("all_matched", lambda summary: True),
        (
            "success_criteria_met",
            lambda summary: summary.get("success_criteria_met") is True,
        ),
        (
            "no_completeness_errors",
            lambda summary: not summary.get("completeness_errors"),
        ),
        (
            "no_ledger_errors",
            lambda summary: not summary.get("ledger_errors"),
        ),
    ]
    rows: list[dict[str, Any]] = []
    for policy_name, include in policies:
        allowed = {
            run_id for run_id, summary in summaries.items()
            if include(summary)
        }
        selected = [
            record for record in records
            if policy_name == "all_matched" or record["run_id"] in allowed
        ]
        for stage in STAGES:
            stage_records = [
                record for record in selected if record["stage"] == stage
            ]
            rows.append(
                {
                    "policy": policy_name,
                    "stage": stage,
                    "correct": sum(
                        int(record["correct"]) for record in stage_records
                    ),
                    "n": len(stage_records),
                    "accuracy": round(_accuracy(stage_records), 6),
                }
            )
    return rows


def _latex_macros(
    stage_rows: list[dict[str, Any]],
    bootstrap_rows: list[dict[str, Any]],
    run_rows: list[dict[str, Any]],
) -> str:
    combined = {
        row["stage"]: row
        for row in stage_rows if row["seed"] == "all"
    }
    bootstrap = {row["stage"]: row for row in bootstrap_rows}
    distribution = {row["correct_stages"]: row for row in run_rows}
    labels = {
        "plan": "Plan",
        "search": "Search",
        "compress": "Compress",
        "write": "Write",
    }
    lines = [
        "% Auto-generated by scripts/analyze_matches.py; do not edit.",
    ]
    for stage in STAGES:
        label = labels[stage]
        lines.append(
            f"\\newcommand{{\\Acc{label}}}{{{combined[stage]['accuracy']:.3f}}}"
        )
        lines.append(
            f"\\newcommand{{\\Acc{label}CILow}}{{{bootstrap[stage]['ci95_low']:.3f}}}"
        )
        lines.append(
            f"\\newcommand{{\\Acc{label}CIHigh}}{{{bootstrap[stage]['ci95_high']:.3f}}}"
        )
    lines.append(
        f"\\newcommand{{\\PerfectRunFraction}}{{{distribution[4]['fraction']:.3f}}}"
    )
    lines.append(
        f"\\newcommand{{\\ZeroRunFraction}}{{{distribution[0]['fraction']:.3f}}}"
    )
    return "\n".join(lines) + "\n"


def analyze(
    match_dir: Path,
    run_dir: Path,
    output_dir: Path,
    bootstrap_repetitions: int = 5000,
    bootstrap_seed: int = 20260802,
) -> dict[str, Any]:
    records = load_match_records(match_dir)
    if not records:
        raise ValueError(f"No *_match.json files found in {match_dir}")
    summaries = load_run_summaries(run_dir)

    stage_rows = stage_accuracy_rows(records)
    variance_rows = seed_variance_rows(records)
    bootstrap_rows = bootstrap_stage_rows(
        records,
        bootstrap_repetitions,
        bootstrap_seed,
    )
    paired_rows = paired_stage_rows(
        records,
        bootstrap_repetitions,
        bootstrap_seed,
    )
    run_rows = run_distribution_rows(records)
    confusions = confusion_rows(records)
    sensitivities = sensitivity_rows(records, summaries)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "stage_accuracy.csv", stage_rows)
    _write_csv(output_dir / "seed_variance.csv", variance_rows)
    _write_csv(output_dir / "stage_accuracy_cluster_bootstrap.csv", bootstrap_rows)
    _write_csv(output_dir / "paired_stage_comparisons.csv", paired_rows)
    _write_csv(output_dir / "run_accuracy_distribution.csv", run_rows)
    _write_csv(output_dir / "persona_confusions.csv", confusions)
    _write_csv(output_dir / "quality_sensitivity.csv", sensitivities)
    (output_dir / "paper_results_macros.tex").write_text(
        _latex_macros(stage_rows, bootstrap_rows, run_rows),
        encoding="utf-8",
    )

    run_ids = sorted({record["run_id"] for record in records})
    summary = {
        "schema_version": 1,
        "source_match_dir": str(match_dir),
        "source_run_dir": str(run_dir),
        "reports": len(run_ids),
        "records": len(records),
        "tasks": len({record["taskid"] for record in records}),
        "seeds": sorted({record["seed"] for record in records}),
        "stages": list(STAGES),
        "bootstrap": {
            "unit": "taskid",
            "repetitions": bootstrap_repetitions,
            "seed": bootstrap_seed,
            "interval": "percentile_95",
        },
        "stage_accuracy": stage_rows,
        "seed_variance": variance_rows,
        "stage_accuracy_cluster_bootstrap": bootstrap_rows,
        "paired_stage_comparisons": paired_rows,
        "run_accuracy_distribution": run_rows,
        "quality_sensitivity": sensitivities,
        "notes": [
            "McNemar p-values are unclustered descriptive checks.",
            "Primary uncertainty intervals use task-level cluster bootstrap.",
            "Regenerate after SHA-256 matcher outputs or new seeds are added.",
        ],
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260802)
    args = parser.parse_args()

    summary = analyze(
        args.match_dir,
        args.run_dir,
        args.output_dir,
        bootstrap_repetitions=args.bootstrap_repetitions,
        bootstrap_seed=args.bootstrap_seed,
    )
    print(
        f"Analyzed {summary['reports']} reports, "
        f"{summary['tasks']} tasks, seeds={summary['seeds']}"
    )
    print(f"Results → {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
