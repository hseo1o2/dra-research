from scripts.analyze_matcher_agreement import analyze, cohen_kappa


def _records(model: str, predictions: list[str]) -> list[dict]:
    rows = []
    for stage, prediction in zip(
        ("plan", "search", "compress", "write"), predictions
    ):
        rows.append({
            "run_id": "pilot_task2_User2_seed0",
            "taskid": 2,
            "seed": 0,
            "stage": stage,
            "model": model,
            "predicted_userid": prediction,
            "correct": prediction == "User2",
            "candidate_userids": ["User1", "User2", "User3"],
            "shuffled_order": ["User3", "User2", "User1"],
        })
    return rows


def test_cohen_kappa_perfect_agreement() -> None:
    result = cohen_kappa(["a", "b", "a"], ["a", "b", "a"])
    assert result["observed_agreement"] == 1
    assert result["cohen_kappa"] == 1


def test_analyze_pairs_stages_and_correctness() -> None:
    solar = _records("solar-pro", ["User2", "User1", "User2", "User3"])
    secondary = _records(
        "gpt-5.4-nano", ["User2", "User2", "User2", "User1"]
    )

    result = analyze(solar, secondary, expected_pairs=4)

    overall = next(
        row for row in result["agreement"] if row["stage"] == "all"
    )
    assert overall["n"] == 4
    assert overall["observed_agreement"] == 0.5
    assert overall["both_correct"] == 2
    assert overall["solar_only_correct"] == 0
    assert overall["secondary_only_correct"] == 1
