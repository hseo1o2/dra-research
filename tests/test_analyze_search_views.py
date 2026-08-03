from scripts.analyze_search_views import audit_protocol


def _row(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "gt_userid": "User1",
        "candidate_userids": ["User1", "User2", "User3"],
        "shuffled_order": ["User2", "User1", "User3"],
        "shuffle_algorithm": "sha256",
        "shuffle_seed": 123,
    }


def test_protocol_audit_accepts_identical_candidate_order() -> None:
    conditions = {
        name: [_row("pilot_task1_User1_seed0")]
        for name in ("full", "queries", "snippets")
    }

    result = audit_protocol(conditions)

    assert result["passed"] is True
    assert result["candidate_set_matches"] == 2
    assert result["candidate_order_matches"] == 2
