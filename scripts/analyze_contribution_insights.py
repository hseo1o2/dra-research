"""Cross-condition analysis for paper contribution claims.

This script is network-free. It compares the final two-seed Solar matches with
two-seed non-LLM baselines, generation seeds, identifier masking, and adjacent
stage transitions. Outputs are intended for manuscript claim selection rather
than for replacing the primary analysis.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_matches import (
    STAGES,
    _exact_mcnemar_p,
    _percentile,
    load_match_records,
)

DEFAULT_SOLAR = ROOT / "runs" / "confirmatory" / "matches_sha256"
DEFAULT_BASELINES = (
    ROOT / "runs" / "confirmatory" / "baselines_sha256_seed0",
    ROOT / "runs" / "confirmatory" / "baselines_sha256_seed1",
)
DEFAULT_MASKED_ANALYSIS = (
    ROOT / "runs" / "confirmatory" / "analysis_masked_sha256"
)
DEFAULT_QUALITY = (
    ROOT / "runs" / "confirmatory" / "analysis_sha256"
    / "quality_sensitivity.csv"
)
DEFAULT_OUTPUT = ROOT / "paper" / "analysis" / "contribution_insights.json"
SEED_SUFFIX = re.compile(r"_seed\d+$")


def _cluster_bootstrap(
    rows: list[dict[str, Any]],
    statistic: Callable[[list[dict[str, Any]]], float],
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
        values.append(statistic(sample))
    return _percentile(values, 0.025), _percentile(values, 0.975)


def _paired_method_comparisons(
    solar: list[dict[str, Any]],
    baseline_dirs: list[Path],
    repetitions: int,
    seed: int,
) -> list[dict[str, Any]]:
    solar_by_key = {
        (row["run_id"], row["stage"]): row
        for row in solar
    }
    output: list[dict[str, Any]] = []
    methods = ("bm25", "embedding", "random")
    for method_index, method in enumerate(methods):
        baseline: list[dict[str, Any]] = []
        for baseline_dir in baseline_dirs:
            baseline.extend(
                load_match_records_from_glob(
                    baseline_dir, f"*_{method}_match.json"
                )
            )
        for scope_index, (scope, scope_seed) in enumerate(
            (("seed0", 0), ("seed1", 1), ("all", None))
        ):
            scoped = [
                row
                for row in baseline
                if scope_seed is None or row["seed"] == scope_seed
            ]
            for stage_index, stage in enumerate(STAGES):
                paired: list[dict[str, Any]] = []
                solar_correct_baseline_wrong = 0
                solar_wrong_baseline_correct = 0
                for row in scoped:
                    if row["stage"] != stage:
                        continue
                    other = solar_by_key[(row["run_id"], stage)]
                    difference = int(other["correct"]) - int(row["correct"])
                    paired.append(
                        {"taskid": row["taskid"], "difference": difference}
                    )
                    solar_correct_baseline_wrong += int(
                        other["correct"] and not row["correct"]
                    )
                    solar_wrong_baseline_correct += int(
                        not other["correct"] and row["correct"]
                    )
                statistic = lambda sample: sum(  # noqa: E731
                    item["difference"] for item in sample
                ) / len(sample)
                low, high = _cluster_bootstrap(
                    paired,
                    statistic,
                    repetitions,
                    seed + method_index * 100 + scope_index * 10
                    + stage_index,
                )
                output.append(
                    {
                        "scope": scope,
                        "baseline": method,
                        "stage": stage,
                        "solar_minus_baseline": round(
                            statistic(paired), 6
                        ),
                        "ci95_low": round(low, 6),
                        "ci95_high": round(high, 6),
                        "solar_correct_baseline_wrong": (
                            solar_correct_baseline_wrong
                        ),
                        "solar_wrong_baseline_correct": (
                            solar_wrong_baseline_correct
                        ),
                        "mcnemar_exact_p_unclustered": round(
                            _exact_mcnemar_p(
                                solar_correct_baseline_wrong,
                                solar_wrong_baseline_correct,
                            ),
                            8,
                        ),
                        "n_reports": len(paired),
                    }
                )
    return output


def load_match_records_from_glob(
    directory: Path, pattern: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob(pattern)):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for row in raw:
            match = re.search(r"_task(?P<taskid>\d+)_.*_seed(?P<seed>\d+)$",
                              row["run_id"])
            if match is None:
                raise ValueError(f"Cannot parse run ID {row['run_id']}")
            records.append(
                {
                    **row,
                    "taskid": int(match.group("taskid")),
                    "seed": int(match.group("seed")),
                    "correct": bool(row["correct"]),
                }
            )
    return records


def _seed_comparisons(
    solar: list[dict[str, Any]],
    repetitions: int,
    seed: int,
) -> list[dict[str, Any]]:
    keyed = {
        (SEED_SUFFIX.sub("", row["run_id"]), row["stage"], row["seed"]): row
        for row in solar
    }
    output: list[dict[str, Any]] = []
    for stage_index, stage in enumerate(STAGES):
        paired: list[dict[str, Any]] = []
        seed0_correct_seed1_wrong = 0
        seed0_wrong_seed1_correct = 0
        bases = sorted(
            {
                SEED_SUFFIX.sub("", row["run_id"])
                for row in solar
                if row["stage"] == stage
            }
        )
        for base in bases:
            first = keyed[(base, stage, 0)]
            second = keyed[(base, stage, 1)]
            paired.append(
                {
                    "taskid": first["taskid"],
                    "difference": (
                        int(second["correct"]) - int(first["correct"])
                    ),
                }
            )
            seed0_correct_seed1_wrong += int(
                first["correct"] and not second["correct"]
            )
            seed0_wrong_seed1_correct += int(
                not first["correct"] and second["correct"]
            )
        statistic = lambda sample: sum(  # noqa: E731
            row["difference"] for row in sample
        ) / len(sample)
        low, high = _cluster_bootstrap(
            paired, statistic, repetitions, seed + stage_index
        )
        output.append(
            {
                "stage": stage,
                "seed1_minus_seed0": round(statistic(paired), 6),
                "ci95_low": round(low, 6),
                "ci95_high": round(high, 6),
                "seed0_correct_seed1_wrong": seed0_correct_seed1_wrong,
                "seed0_wrong_seed1_correct": seed0_wrong_seed1_correct,
                "mcnemar_exact_p_unclustered": round(
                    _exact_mcnemar_p(
                        seed0_correct_seed1_wrong,
                        seed0_wrong_seed1_correct,
                    ),
                    8,
                ),
                "n_paired_reports": len(paired),
            }
        )
    return output


def _transition_flows(
    solar: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key = {
        (row["run_id"], row["stage"]): row
        for row in solar
    }
    pairs = (
        ("plan", "search"),
        ("search", "compress"),
        ("compress", "write"),
    )
    output: list[dict[str, Any]] = []
    run_ids = sorted({row["run_id"] for row in solar})
    for first_stage, second_stage in pairs:
        counts = {
            "correct_to_correct": 0,
            "correct_to_wrong": 0,
            "wrong_to_correct": 0,
            "wrong_to_wrong": 0,
        }
        for run_id in run_ids:
            first = bool(by_key[(run_id, first_stage)]["correct"])
            second = bool(by_key[(run_id, second_stage)]["correct"])
            key = (
                f"{'correct' if first else 'wrong'}_to_"
                f"{'correct' if second else 'wrong'}"
            )
            counts[key] += 1
        output.append(
            {
                "from_stage": first_stage,
                "to_stage": second_stage,
                **counts,
                "net_gain": (
                    counts["wrong_to_correct"]
                    - counts["correct_to_wrong"]
                ),
                "n_reports": len(run_ids),
            }
        )
    return output


def _recovery_summary(solar: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {
        (row["run_id"], row["stage"]): bool(row["correct"])
        for row in solar
    }
    run_ids = sorted({row["run_id"] for row in solar})
    plan_to_search_losses = [
        run_id
        for run_id in run_ids
        if by_key[(run_id, "plan")] and not by_key[(run_id, "search")]
    ]
    search_errors = [
        run_id for run_id in run_ids if not by_key[(run_id, "search")]
    ]
    return {
        "planning_correct_search_wrong": len(plan_to_search_losses),
        "of_planning_losses_recovered_by_compression": sum(
            by_key[(run_id, "compress")]
            for run_id in plan_to_search_losses
        ),
        "of_planning_losses_recovered_by_writing": sum(
            by_key[(run_id, "write")]
            for run_id in plan_to_search_losses
        ),
        "search_wrong": len(search_errors),
        "search_wrong_but_compression_correct": sum(
            by_key[(run_id, "compress")] for run_id in search_errors
        ),
        "search_wrong_but_writing_correct": sum(
            by_key[(run_id, "write")] for run_id in search_errors
        ),
    }


def analyze(
    solar_dir: Path = DEFAULT_SOLAR,
    baseline_dirs: list[Path] | None = None,
    masked_analysis_dir: Path | None = DEFAULT_MASKED_ANALYSIS,
    repetitions: int = 5000,
    seed: int = 20260803,
) -> dict[str, Any]:
    solar = load_match_records(solar_dir)
    resolved_baseline_dirs = baseline_dirs or list(DEFAULT_BASELINES)
    mask_deltas = None
    masking_reports = 0
    if masked_analysis_dir is not None:
        mask_summary = json.loads(
            (masked_analysis_dir / "masked_control_summary.json").read_text(
                encoding="utf-8"
            )
        )
        mask_deltas = mask_summary["original_vs_masked_deltas"]
        masking_reports = int(
            mask_summary.get("population", {}).get("reports", 120)
        )
    return {
        "schema_version": 1,
        "analysis_role": "cross-condition contribution claim analysis",
        "external_api_calls": 0,
        "population": {
            "primary_reports": len({row["run_id"] for row in solar}),
            "primary_tasks": len({row["taskid"] for row in solar}),
            "seeds": sorted({row["seed"] for row in solar}),
            "baseline_reports": sum(
                len(
                    {
                        row["run_id"]
                        for row in load_match_records_from_glob(
                            baseline_dir, "*_bm25_match.json"
                        )
                    }
                )
                for baseline_dir in resolved_baseline_dirs
            ),
            "masking_reports": masking_reports,
        },
        "solar_vs_baselines": _paired_method_comparisons(
            solar, resolved_baseline_dirs, repetitions, seed
        ),
        "seed1_vs_seed0": _seed_comparisons(
            solar, repetitions, seed + 100
        ),
        "adjacent_stage_flows": _transition_flows(solar),
        "recovery": _recovery_summary(solar),
        "identifier_masked_minus_original": mask_deltas,
        "claim_boundaries": [
            "Acc@1 measures persona recoverability, not report utility.",
            (
                "Baseline comparisons cover seeds 0 and 1; identifier "
                "masking is omitted pending a candidate-protocol-matched "
                "rerun."
                if masked_analysis_dir is None
                else "Baseline and masking comparisons cover seeds 0 and 1."
            ),
            "Task-cluster bootstrap intervals are primary; unclustered "
            "McNemar p-values are descriptive.",
            "Seed comparisons use only two generation seeds.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solar-dir", type=Path, default=DEFAULT_SOLAR)
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        action="append",
        dest="baseline_dirs",
        help="Repeat for multiple seed-specific baseline directories",
    )
    parser.add_argument(
        "--masked-analysis-dir", type=Path, default=DEFAULT_MASKED_ANALYSIS
    )
    parser.add_argument(
        "--skip-masked",
        action="store_true",
        help=(
            "Omit identifier-masked results when they do not share the "
            "current candidate protocol"
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260803)
    args = parser.parse_args()
    result = analyze(
        solar_dir=args.solar_dir,
        baseline_dirs=args.baseline_dirs,
        masked_analysis_dir=(
            None if args.skip_masked else args.masked_analysis_dir
        ),
        repetitions=args.bootstrap_repetitions,
        seed=args.bootstrap_seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Contribution analysis → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
