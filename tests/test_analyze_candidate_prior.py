from pathlib import Path

from scripts.analyze_candidate_prior import (
    centrality_prediction,
    protocol_trajectory,
)


def test_centrality_prediction_is_order_independent() -> None:
    tokens = {
        "User1": {"a", "b", "c", "d"},
        "User2": {"a", "b", "c"},
        "User3": {"a"},
    }
    first, _ = centrality_prediction(
        ["User1", "User2", "User3"], tokens
    )
    second, _ = centrality_prediction(
        ["User3", "User1", "User2"], tokens
    )
    assert first == second == "User2"


def test_protocol_trajectory_reads_four_stages(tmp_path: Path) -> None:
    stages = ("plan", "search", "compress", "write")
    for index in range(120):
        run_id = f"pilot_task{index // 3}_User{index % 3}_seed0"
        rows = [{
            "run_id": run_id,
            "stage": stage,
            "correct": stage in ("plan", "write"),
            "gt_userid": f"User{index % 3}",
            "predicted_userid": f"User{index % 3}",
            "candidate_userids": ["User0", "User1", "User2"],
            "shuffled_order": ["User2", "User0", "User1"],
        } for stage in stages]
        (tmp_path / f"{run_id}_match.json").write_text(
            __import__("json").dumps(rows), encoding="utf-8"
        )
    result = protocol_trajectory(tmp_path, "test")
    assert result["stage_accuracy"]["plan"] == 1
    assert result["stage_accuracy"]["search"] == 0
    assert result["search_to_writing"] == 1
