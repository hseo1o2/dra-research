from scripts.evaluate_ablation_generation_gate import evaluate


def _quality(completeness: int = 0, ledger: int = 0) -> dict:
    return {
        "completed_runs": 15,
        "schema_valid_runs": 15,
        "success_criteria_met_runs": 15 - completeness,
        "completeness_issue_runs": completeness,
        "ledger_issue_runs": ledger,
        "execution_error_runs": 0,
        "total_tokens": 100,
        "queries_successful": 20,
        "queries_failed": 1,
    }


def test_generation_gate_requires_both_conditions_to_pass() -> None:
    result = evaluate(_quality(), _quality(completeness=3))

    assert not result["generation_gate_passed"]
    assert not result["seed1_authorized_by_this_gate"]
    assert result["conditions"]["actionable_only"][
        "generation_gate_passed"
    ]
    assert not result["conditions"]["identity_only"][
        "generation_gate_passed"
    ]


def test_generation_gate_rejects_ledger_issue() -> None:
    result = evaluate(_quality(ledger=1), _quality())

    assert not result["generation_gate_passed"]
    assert not result["conditions"]["actionable_only"]["checks"][
        "ledger_clean"
    ]
