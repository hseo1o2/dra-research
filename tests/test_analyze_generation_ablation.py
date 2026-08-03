import json
from pathlib import Path

from scripts.analyze_generation_ablation import (
    comparability,
    generation_quality_gate,
    paired_condition_rows,
    quality_summary,
)


def _match_record(
    *,
    condition: str,
    task_id: str = "task2",
    user_id: str = "User2",
    seed: int = 0,
    stage: str = "write",
    correct: bool = True,
    candidate_userids: list[str] | None = None,
) -> dict:
    candidates = candidate_userids or ["User3", "User2", "User1"]
    return {
        "condition": condition,
        "run_id": f"ablation_{condition}_{task_id}_{user_id}_seed{seed}",
        "taskid": int(task_id.removeprefix("task")),
        "gt_userid": user_id,
        "seed": seed,
        "stage": stage,
        "correct": correct,
        "candidate_userids": candidates,
        "shuffled_order": candidates,
    }


def test_comparability_accepts_identical_candidate_order() -> None:
    full = [_match_record(condition="full")]
    ablation = [_match_record(condition="actionable_only")]

    result = comparability(full, ablation, "full", "actionable_only")

    assert result["directly_comparable"] is True
    assert result["left_only_pairs"] == 0
    assert result["right_only_pairs"] == 0
    assert result["candidate_order_matches"] == 1


def test_comparability_rejects_candidate_order_mismatch() -> None:
    full = [_match_record(condition="full")]
    ablation = [
        _match_record(
            condition="identity_only",
            candidate_userids=["User2", "User3", "User1"],
        )
    ]

    result = comparability(full, ablation, "full", "identity_only")

    assert result["directly_comparable"] is False
    assert result["candidate_order_matches"] == 0


def test_paired_condition_rows_computes_condition_minus_full() -> None:
    full = [
        _match_record(condition="full", stage="plan", correct=False),
        _match_record(condition="full", stage="search", correct=True),
        _match_record(condition="full", stage="compress", correct=True),
        _match_record(condition="full", stage="write", correct=True),
    ]
    ablation = [
        _match_record(
            condition="actionable_only", stage="plan", correct=True
        ),
        _match_record(condition="actionable_only", stage="search", correct=False),
        _match_record(condition="actionable_only", stage="compress", correct=True),
        _match_record(condition="actionable_only", stage="write", correct=False),
    ]

    rows = paired_condition_rows(
        ablation,
        full,
        "actionable_only",
        "full",
        repetitions=100,
        seed=7,
    )

    by_stage = {row["stage"]: row for row in rows}
    assert by_stage["plan"]["left_minus_right"] == 1
    assert by_stage["search"]["left_minus_right"] == -1
    assert by_stage["compress"]["left_minus_right"] == 0
    assert by_stage["write"]["left_minus_right"] == -1


def test_quality_summary_counts_valid_and_successful_reports(
    tmp_path: Path,
) -> None:
    reports = [
        {
            "schema_valid": True,
            "success_criteria_met": True,
            "execution_error": None,
            "run_id": "ablation_actionable_only_task2_User2_seed0",
            "completeness_errors": [],
            "ledger_errors": [],
            "token_ledger": {
                "total_tokens": 100,
                "queries_attempted": 7,
                "queries_successful": 6,
            },
        },
        {
            "schema_valid": True,
            "success_criteria_met": False,
            "execution_error": None,
            "run_id": "ablation_actionable_only_task2_User6_seed0",
            "completeness_errors": ["missing topic"],
            "ledger_errors": [],
            "token_ledger": {
                "total_tokens": 90,
                "queries_attempted": 7,
                "queries_successful": 5,
            },
        },
    ]
    for index, report in enumerate(reports):
        (tmp_path / f"report_{index}_summary.json").write_text(
            json.dumps(report),
            encoding="utf-8",
        )

    result = quality_summary("actionable_only", tmp_path, expected_reports=2)

    assert result["completed_reports"] == 2
    assert result["schema_valid_reports"] == 2
    assert result["success_criteria_met_reports"] == 1
    assert result["completeness_issue_reports"] == 1
    assert result["execution_error_reports"] == 0
    assert result["total_tokens"] == 190
    assert result["queries_attempted"] == 14
    assert result["queries_successful"] == 11


def test_generation_quality_gate_requires_all_reports_to_pass(
    tmp_path: Path,
) -> None:
    actionable = tmp_path / "actionable"
    identity = tmp_path / "identity"
    actionable.mkdir()
    identity.mkdir()
    base = {
        "schema_valid": True,
        "success_criteria_met": True,
        "completeness_errors": [],
        "execution_error": None,
        "ledger_errors": [],
        "token_ledger": {},
    }
    for condition, directory in [
        ("actionable_only", actionable),
        ("identity_only", identity),
    ]:
        report = {
            **base,
            "run_id": f"ablation_{condition}_task2_User2_seed0",
        }
        (directory / "report_summary.json").write_text(
            json.dumps(report),
            encoding="utf-8",
        )

    passing = generation_quality_gate(actionable, identity, 1)
    assert passing["passed"] is True

    failed_report = {
        **base,
        "run_id": "ablation_identity_only_task2_User2_seed0",
        "success_criteria_met": False,
        "completeness_errors": ["missing topic"],
    }
    (identity / "report_summary.json").write_text(
        json.dumps(failed_report),
        encoding="utf-8",
    )
    failing = generation_quality_gate(actionable, identity, 1)
    assert failing["passed"] is False
    assert "completeness issue" in failing["checks"][1]["reasons"]
