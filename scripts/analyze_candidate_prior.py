"""Audit attribution-candidate construction priors without model/API calls.

The per-GT protocol selects two nearest actionable-profile neighbors around
the ground-truth persona. This script measures how often a candidate-only
centrality heuristic can identify that construction center, then compares
the stage trajectory with the symmetric task-shared candidate protocol.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_matches import STAGES, load_match_records
from scripts.build_manifest import actionable_tokens, jaccard, load_jsonl

DEFAULT_HARDNEG = ROOT / "runs" / "confirmatory" / "matches_hardneg_v1"
DEFAULT_SHARED = ROOT / "runs" / "confirmatory" / "matches_sha256"
DEFAULT_OUTPUT = (
    ROOT / "runs" / "confirmatory" / "analysis_candidate_prior"
    / "candidate_prior_summary.json"
)


def centrality_prediction(
    candidate_userids: list[str],
    tokens_by_userid: dict[str, set[str]],
) -> tuple[str, dict[str, float]]:
    if len(candidate_userids) < 2:
        raise ValueError("At least two candidates are required")
    scores = {
        userid: sum(
            jaccard(tokens_by_userid[userid], tokens_by_userid[other])
            for other in candidate_userids
            if other != userid
        ) / (len(candidate_userids) - 1)
        for userid in candidate_userids
    }
    # User-ID tie break is independent of stored candidate order.
    prediction = sorted(
        scores, key=lambda userid: (-scores[userid], userid)
    )[0]
    return prediction, scores


def _cluster_bootstrap(
    rows: list[dict[str, Any]],
    repetitions: int,
    seed: int,
) -> tuple[float, float]:
    by_task: dict[int, list[int]] = defaultdict(list)
    for row in rows:
        by_task[int(row["taskid"])].append(int(row["correct"]))
    taskids = sorted(by_task)
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(repetitions):
        sampled = [rng.choice(taskids) for _ in taskids]
        values = [
            value for taskid in sampled for value in by_task[taskid]
        ]
        estimates.append(sum(values) / len(values))
    estimates.sort()
    low_index = max(0, int(0.025 * repetitions) - 1)
    high_index = min(repetitions - 1, int(0.975 * repetitions) - 1)
    return estimates[low_index], estimates[high_index]


def candidate_prior_audit(
    manifest: dict[str, Any],
    personas: list[dict[str, Any]],
    repetitions: int = 5000,
    seed: int = 20260803,
) -> dict[str, Any]:
    tokens = {
        str(persona["userid"]): actionable_tokens(persona)
        for persona in personas
    }
    rows: list[dict[str, Any]] = []
    margins: list[float] = []
    for task in manifest["pdr_bench"]["confirmatory"]:
        for experiment in task["experiments"]:
            candidates = list(
                experiment["attribution_candidate_set_n3"]
            )
            prediction, scores = centrality_prediction(candidates, tokens)
            ranked = sorted(scores.values(), reverse=True)
            margins.append(ranked[0] - ranked[1])
            rows.append({
                "taskid": int(task["taskid"]),
                "gt_userid": str(experiment["gt_userid"]),
                "predicted_userid": prediction,
                "correct": prediction == experiment["gt_userid"],
            })
    accuracy = sum(row["correct"] for row in rows) / len(rows)
    low, high = _cluster_bootstrap(rows, repetitions, seed)
    return {
        "heuristic": "highest mean pairwise actionable-token Jaccard",
        "artifact_text_used": False,
        "candidate_sets": len(rows),
        "task_clusters": len({row["taskid"] for row in rows}),
        "correct": sum(row["correct"] for row in rows),
        "accuracy": round(accuracy, 6),
        "chance": round(1 / 3, 6),
        "task_cluster_bootstrap_ci95": [
            round(low, 6), round(high, 6)
        ],
        "bootstrap_repetitions": repetitions,
        "bootstrap_seed": seed,
        "mean_top_score_margin": round(sum(margins) / len(margins), 6),
    }


def protocol_trajectory(
    match_dir: Path,
    protocol: str,
) -> dict[str, Any]:
    records = load_match_records(match_dir)
    by_stage: dict[str, list[bool]] = defaultdict(list)
    for row in records:
        by_stage[str(row["stage"])].append(bool(row["correct"]))
    counts = {stage: len(by_stage[stage]) for stage in STAGES}
    if set(counts.values()) != {120}:
        raise ValueError(
            f"{protocol}: expected 120 decisions per stage, got {counts}"
        )
    accuracy = {
        stage: round(
            sum(by_stage[stage]) / len(by_stage[stage]), 6
        )
        for stage in STAGES
    }
    return {
        "protocol": protocol,
        "match_dir": str(match_dir),
        "reports": 120,
        "stage_accuracy": accuracy,
        "planning_to_search": round(
            accuracy["search"] - accuracy["plan"], 6
        ),
        "search_to_writing": round(
            accuracy["write"] - accuracy["search"], 6
        ),
    }


def analyze(
    manifest: dict[str, Any],
    personas: list[dict[str, Any]],
    hardneg_dir: Path,
    shared_dir: Path,
    repetitions: int = 5000,
    seed: int = 20260803,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "external_api_calls": 0,
        "candidate_only_prior": candidate_prior_audit(
            manifest, personas, repetitions, seed
        ),
        "protocol_sensitivity": [
            protocol_trajectory(
                hardneg_dir, "per_gt_actionable_hard_negative"
            ),
            protocol_trajectory(
                shared_dir, "task_shared_candidate_cohort"
            ),
        ],
        "interpretation_boundary": (
            "A candidate-only prior can affect absolute Acc@1. Because each "
            "report keeps the same candidate set at all four stages, it "
            "cannot alone generate a within-report stage transition. The "
            "task-shared protocol is a symmetric secondary sensitivity, not "
            "a replacement for the frozen primary protocol."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "manifest.json"
    )
    parser.add_argument(
        "--personas",
        type=Path,
        default=(
            ROOT / "data" / "pdr-bench" / "persona_data"
            / "personas_en.jsonl"
        ),
    )
    parser.add_argument("--hardneg-dir", type=Path, default=DEFAULT_HARDNEG)
    parser.add_argument("--shared-dir", type=Path, default=DEFAULT_SHARED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260803)
    args = parser.parse_args()

    result = analyze(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        load_jsonl(args.personas),
        args.hardneg_dir,
        args.shared_dir,
        args.bootstrap_repetitions,
        args.bootstrap_seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(f"Candidate-prior analysis → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

