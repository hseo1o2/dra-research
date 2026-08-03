from scripts.analyze_masked_control import (
    comparability_checks,
    trajectory_retention,
)


def _records(order_by_condition: str = "same"):
    original = []
    masked = []
    stage_values = {
        "plan": (True, True),
        "search": (False, False),
        "compress": (False, True),
        "write": (True, True),
    }
    for stage, (original_correct, masked_correct) in stage_values.items():
        base = {
            "run_id": "pilot_task1_User1_seed0",
            "stage": stage,
            "taskid": 1,
            "seed": 0,
            "gt_userid": "User1",
            "candidate_userids": ["User1", "User2", "User3"],
        }
        original.append(
            {
                **base,
                "correct": original_correct,
                "shuffled_order": ["User1", "User2", "User3"],
            }
        )
        masked.append(
            {
                **base,
                "correct": masked_correct,
                "shuffled_order": (
                    ["User1", "User2", "User3"]
                    if order_by_condition == "same"
                    else ["User2", "User1", "User3"]
                ),
            }
        )
    return original, masked


def test_comparability_detects_candidate_order_confound():
    original, masked = _records("different")
    checks = comparability_checks(original, masked)
    assert checks["candidate_set_mismatches"] == 0
    assert checks["candidate_order_matches"] == 0
    assert checks["direct_condition_effect_is_identified"] is False


def test_comparability_accepts_identical_order():
    original, masked = _records("same")
    checks = comparability_checks(original, masked)
    assert checks["direct_condition_effect_is_identified"] is True


def test_trajectory_retention_uses_within_condition_pattern():
    _original, masked = _records("different")
    result = trajectory_retention(masked, repetitions=100, bootstrap_seed=7)
    assert result["observed"] is True
    assert result["planning_to_search_pp"] == -100.0
    assert result["search_to_write_pp"] == 100.0
