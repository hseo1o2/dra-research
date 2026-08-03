from __future__ import annotations

import json

import pytest

from scripts.analyze_matches import (
    _exact_mcnemar_p,
    analyze,
    load_match_records,
)


def _record(run_id: str, stage: str, correct: bool) -> dict:
    return {
        "run_id": run_id,
        "stage": stage,
        "gt_userid": "User1",
        "predicted_userid": "User1" if correct else "User2",
        "correct": correct,
    }


def test_analysis_end_to_end(tmp_path):
    match_dir = tmp_path / "matches"
    run_dir = tmp_path / "runs"
    output_dir = tmp_path / "analysis"
    match_dir.mkdir()
    run_dir.mkdir()

    runs = {
        "pilot_task1_User1_seed0": [True, False, True, True],
        "pilot_task1_User2_seed0": [False, False, True, True],
        "pilot_task2_User1_seed0": [True, True, True, True],
    }
    for run_id, correctness in runs.items():
        payload = [
            _record(run_id, stage, correct)
            for stage, correct in zip(
                ("plan", "search", "compress", "write"),
                correctness,
            )
        ]
        (match_dir / f"{run_id}_match.json").write_text(json.dumps(payload))
        summary = {
            "run_id": run_id,
            "success_criteria_met": "User2" not in run_id,
            "completeness_errors": (
                ["missing source"] if "User2" in run_id else []
            ),
            "ledger_errors": [],
        }
        (run_dir / f"{run_id}_summary.json").write_text(json.dumps(summary))

    result = analyze(
        match_dir,
        run_dir,
        output_dir,
        bootstrap_repetitions=100,
        bootstrap_seed=7,
    )

    assert result["reports"] == 3
    assert result["tasks"] == 2
    combined = {
        row["stage"]: row
        for row in result["stage_accuracy"]
        if row["seed"] == "all"
    }
    assert combined["plan"]["accuracy"] == pytest.approx(2 / 3, abs=1e-6)
    assert combined["search"]["accuracy"] == pytest.approx(1 / 3, abs=1e-6)
    assert combined["compress"]["accuracy"] == 1.0
    assert combined["write"]["accuracy"] == 1.0
    assert all(
        row["population_sd_across_seeds"] is None
        for row in result["seed_variance"]
    )
    assert (output_dir / "paper_results_macros.tex").exists()
    assert (output_dir / "quality_sensitivity.csv").exists()


def test_duplicate_stage_records_are_rejected(tmp_path):
    match_dir = tmp_path / "matches"
    match_dir.mkdir()
    run_id = "pilot_task1_User1_seed0"
    payload = [
        _record(run_id, "plan", True),
        _record(run_id, "plan", False),
    ]
    (match_dir / "duplicate_match.json").write_text(json.dumps(payload))

    try:
        load_match_records(match_dir)
    except ValueError as exc:
        assert "Duplicate match records" in str(exc)
    else:
        raise AssertionError("duplicate records must fail")


def test_exact_mcnemar_edge_cases():
    assert _exact_mcnemar_p(0, 0) == 1.0
    assert _exact_mcnemar_p(1, 1) == 1.0
    assert 0 < _exact_mcnemar_p(0, 5) < 0.1
