from scripts.analyze_contribution_insights import (
    _recovery_summary,
    _transition_flows,
)


def _records():
    stages = ("plan", "search", "compress", "write")
    patterns = {
        "run_a_seed0": (True, False, True, True),
        "run_b_seed0": (False, False, False, True),
    }
    rows = []
    for run_id, values in patterns.items():
        for stage, correct in zip(stages, values):
            rows.append(
                {
                    "run_id": run_id,
                    "stage": stage,
                    "correct": correct,
                    "taskid": 1,
                    "seed": 0,
                }
            )
    return rows


def test_transition_flows_count_loss_and_recovery():
    flows = _transition_flows(_records())
    assert flows[0]["correct_to_wrong"] == 1
    assert flows[1]["wrong_to_correct"] == 1
    assert flows[2]["wrong_to_correct"] == 1


def test_recovery_summary_tracks_search_errors():
    result = _recovery_summary(_records())
    assert result["planning_correct_search_wrong"] == 1
    assert result["of_planning_losses_recovered_by_writing"] == 1
    assert result["search_wrong"] == 2
    assert result["search_wrong_but_writing_correct"] == 2
