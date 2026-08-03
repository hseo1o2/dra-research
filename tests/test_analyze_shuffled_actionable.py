from scripts.analyze_matches import STAGES
from scripts.analyze_shuffled_actionable import analyze
from scripts.llm_matcher import deterministic_candidate_order


def _manifest() -> dict:
    return {
        "pdr_bench": {
            "ablation_subset": {"taskids": [2]},
            "confirmatory": [{
                "taskid": 2,
                "personas_n3": ["User2", "User6", "User7"],
            }],
        }
    }


def _rows(prefix: str, predictions: list[str]) -> list[dict]:
    rows = []
    for user, prediction in zip(["User2", "User6", "User7"], predictions):
        for stage in STAGES:
            run_id = f"{prefix}_task2_{user}_seed0"
            candidates = ["User2", "User6", "User7"]
            rows.append({
                "run_id": run_id,
                "stage": stage,
                "candidate_userids": candidates,
                "shuffled_order": deterministic_candidate_order(
                    run_id, stage, candidates
                ),
                "predicted_userid": prediction,
            })
    return rows


def test_analyze_shuffled_actionable_tracks_donor_following() -> None:
    shuffled = _rows(
        "ablation_shuffled_actionable",
        ["User6", "User7", "User2"],
    )
    result = analyze(
        _manifest(),
        shuffled,
        repetitions=50,
        expected_reports=3,
        strict_run_ids={
            "ablation_shuffled_actionable_task2_User2_seed0",
            "ablation_shuffled_actionable_task2_User6_seed0",
            "ablation_shuffled_actionable_task2_User7_seed0",
        },
    )

    assert result["candidate_order_sha256_verified"] == 12
    assert result["strict_quality_sensitivity"]["reports"] == 3
    for row in result["stage_results"]:
        assert row["donor_predictions"] == 3
        assert row["shell_predictions"] == 0
        assert row["p_donor"] == 1.0
        assert row["donor_minus_shell"] == 1.0
