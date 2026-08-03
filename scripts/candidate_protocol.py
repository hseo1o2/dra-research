"""Frozen attribution-candidate lookup shared by all matchers."""

from __future__ import annotations

from typing import Any


def parse_pdr_run_id(run_id: str) -> tuple[int, str]:
    parts = run_id.split("_")
    task_token = next(
        (part for part in parts if part.startswith("task")), None
    )
    user_token = next(
        (part for part in parts if part.startswith("User")), None
    )
    if (
        task_token is None
        or user_token is None
        or not task_token[4:].isdigit()
        or not user_token[4:].isdigit()
    ):
        raise ValueError(f"Cannot parse run_id: {run_id}")
    return int(task_token[4:]), user_token


def lookup_pdr_candidates(
    run_id: str,
    manifest: dict[str, Any],
) -> tuple[str, list[str]]:
    """Return GT and the frozen candidate set for one PDR run.

    Full/actionable-only/identity-only runs use the per-GT hard-negative set
    frozen in ``attribution_candidate_set_n3``. Shuffled-actionable uses the
    three-person ablation group because both the identity shell and cyclic
    actionable donor must be present in the matcher candidate set.
    """
    taskid, gt_userid = parse_pdr_run_id(run_id)
    shuffled = run_id.startswith("ablation_shuffled_actionable_")
    pdr = manifest.get("pdr_bench", {})
    for split_name in ("dev", "confirmatory"):
        for task in pdr.get(split_name, []):
            if int(task.get("taskid", -1)) != taskid:
                continue
            experiment = next(
                (
                    row for row in task.get("experiments", [])
                    if row.get("gt_userid") == gt_userid
                ),
                None,
            )
            if experiment is None:
                break
            candidates = (
                list(task.get("personas_n3", []))
                if shuffled
                else list(
                    experiment.get("attribution_candidate_set_n3", [])
                )
            )
            if (
                len(candidates) != 3
                or len(set(candidates)) != 3
                or gt_userid not in candidates
            ):
                raise ValueError(
                    f"Invalid frozen candidates for {run_id}: {candidates}"
                )
            return gt_userid, candidates
    raise ValueError(
        f"run_id {run_id} not found in manifest "
        f"(task={taskid}, gt={gt_userid})"
    )
