"""Analyze whether shuffled-actionable predictions follow donor or shell.

Network-free. Requires 15 shuffled-actionable reports matched at four stages
and verifies their candidate order from the SHA-256 shuffle protocol.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_matches import STAGES, _exact_mcnemar_p, _percentile
from scripts.candidate_protocol import parse_pdr_run_id
from scripts.llm_matcher import deterministic_candidate_order
from scripts.persona_ablation import actionable_donor_userid

DEFAULT_RUN_DIR = ROOT / "runs" / "ablation" / "shuffled_actionable"
DEFAULT_OUTPUT = ROOT / "runs" / "ablation" / "analysis_shuffled_actionable"


def _load_matches(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match_path in sorted(path.glob("*_match.json")):
        value = json.loads(match_path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise ValueError(f"Expected list in {match_path}")
        rows.extend(value)
    return rows


def _donor_map(
    manifest: dict[str, Any],
) -> dict[tuple[int, str], str]:
    taskids = set(manifest["pdr_bench"]["ablation_subset"]["taskids"])
    result: dict[tuple[int, str], str] = {}
    for task in manifest["pdr_bench"]["confirmatory"]:
        if task["taskid"] not in taskids:
            continue
        group = list(task["personas_n3"])
        for shell in group:
            result[(int(task["taskid"]), shell)] = actionable_donor_userid(
                shell, group
            )
    return result


def _stage_summary(
    enriched: list[dict[str, Any]],
    repetitions: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    stage_rows: list[dict[str, Any]] = []
    for stage in STAGES:
        selected = [row for row in enriched if row["stage"] == stage]
        by_task: dict[int, list[float]] = defaultdict(list)
        for row in selected:
            by_task[int(row["taskid"])].append(
                float(row["follows_donor"])
                - float(row["follows_shell"])
            )
        task_values = [mean(values) for values in by_task.values()]
        bootstrap = [
            mean(rng.choices(task_values, k=len(task_values)))
            for _ in range(repetitions)
        ]
        donor_n = sum(row["follows_donor"] for row in selected)
        shell_n = sum(row["follows_shell"] for row in selected)
        other_n = len(selected) - donor_n - shell_n
        stage_rows.append({
            "stage": stage,
            "n": len(selected),
            "donor_predictions": donor_n,
            "shell_predictions": shell_n,
            "other_predictions": other_n,
            "p_donor": donor_n / len(selected),
            "p_shell": shell_n / len(selected),
            "donor_minus_shell": (donor_n - shell_n) / len(selected),
            "task_bootstrap_ci95": [
                _percentile(bootstrap, 0.025),
                _percentile(bootstrap, 0.975),
            ],
            "donor_vs_shell_exact_p": _exact_mcnemar_p(
                donor_n, shell_n
            ),
        })
    return stage_rows


def analyze(
    manifest: dict[str, Any],
    shuffled: list[dict[str, Any]],
    repetitions: int = 5000,
    seed: int = 20260803,
    expected_reports: int = 15,
    strict_run_ids: set[str] | None = None,
) -> dict[str, Any]:
    if len(shuffled) != expected_reports * len(STAGES):
        raise ValueError(
            f"Expected {expected_reports * len(STAGES)} shuffled decisions, "
            f"got {len(shuffled)}"
        )
    donors = _donor_map(manifest)
    enriched: list[dict[str, Any]] = []
    order_mismatches = 0
    for row in shuffled:
        run_id = str(row["run_id"])
        taskid, shell = parse_pdr_run_id(run_id)
        donor = donors[(taskid, shell)]
        candidates = list(row["candidate_userids"])
        if shell not in candidates or donor not in candidates:
            raise ValueError(
                f"Shell/donor missing from candidates for {run_id}"
            )
        expected_order = deterministic_candidate_order(
            run_id,
            str(row["stage"]),
            candidates,
            int(row.get("shuffle_seed", 42)),
        )
        if expected_order != row["shuffled_order"]:
            order_mismatches += 1
        prediction = str(row["predicted_userid"])
        enriched.append({
            "run_id": run_id,
            "taskid": taskid,
            "stage": str(row["stage"]),
            "follows_donor": prediction == donor,
            "follows_shell": prediction == shell,
        })
    if order_mismatches:
        raise ValueError(
            f"Deterministic candidate-order verification failed: "
            f"order_mismatches={order_mismatches}"
        )

    strict_ids = strict_run_ids or set()
    strict_rows = [
        row for row in enriched if row["run_id"] in strict_ids
    ]
    return {
        "schema_version": 2,
        "external_api_calls": 0,
        "population": {
            "reports": expected_reports,
            "stages": list(STAGES),
            "seed": 0,
        },
        "candidate_order_sha256_verified": expected_reports * len(STAGES),
        "stage_results": _stage_summary(enriched, repetitions, seed),
        "strict_quality_sensitivity": {
            "reports": len(strict_ids),
            "stage_results": (
                _stage_summary(strict_rows, repetitions, seed + 100)
                if strict_rows else []
            ),
        },
        "primary_estimand": "P(predicted=donor)-P(predicted=shell)",
        "claim_boundary": (
            "Donor-following is intervention-based evidence about evaluator "
            "recoverability, not user utility or latent-intent recovery."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "manifest.json"
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260803)
    args = parser.parse_args()

    strict_run_ids: set[str] = set()
    for summary_path in args.run_dir.glob(
        "ablation_shuffled_actionable_*_summary.json"
    ):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("success_criteria_met"):
            strict_run_ids.add(str(summary["run_id"]))

    result = analyze(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        _load_matches(args.run_dir / "matches"),
        args.bootstrap_repetitions,
        args.bootstrap_seed,
        strict_run_ids=strict_run_ids,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "shuffled_actionable_summary.json"
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Shuffled-actionable analysis → {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
