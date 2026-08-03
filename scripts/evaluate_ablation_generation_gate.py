"""Evaluate the DEC-006 seed-0 generation gate without external APIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = (
    ROOT / "runs" / "ablation" / "seed0_generation_gate.json"
)


def evaluate_condition(
    quality: dict[str, Any],
    expected_runs: int = 15,
    max_completeness_issues: int = 2,
) -> dict[str, Any]:
    checks = {
        "all_runs_completed": quality["completed_runs"] == expected_runs,
        "all_schema_valid": quality["schema_valid_runs"] == expected_runs,
        "completeness_within_threshold": (
            quality["completeness_issue_runs"]
            <= max_completeness_issues
        ),
        "ledger_clean": quality["ledger_issue_runs"] == 0,
        "no_execution_errors": quality["execution_error_runs"] == 0,
    }
    return {
        "expected_runs": expected_runs,
        "observed": {
            "completed_runs": quality["completed_runs"],
            "schema_valid_runs": quality["schema_valid_runs"],
            "success_criteria_met_runs": (
                quality["success_criteria_met_runs"]
            ),
            "completeness_issue_runs": (
                quality["completeness_issue_runs"]
            ),
            "ledger_issue_runs": quality["ledger_issue_runs"],
            "execution_error_runs": quality["execution_error_runs"],
            "total_tokens": quality["total_tokens"],
            "queries_successful": quality["queries_successful"],
            "queries_failed": quality["queries_failed"],
        },
        "checks": checks,
        "generation_gate_passed": all(checks.values()),
    }


def evaluate(
    actionable: dict[str, Any],
    identity: dict[str, Any],
) -> dict[str, Any]:
    conditions = {
        "actionable_only": evaluate_condition(actionable),
        "identity_only": evaluate_condition(identity),
    }
    return {
        "schema_version": 1,
        "external_api_calls": 0,
        "decision_source": "DEC-006",
        "conditions": conditions,
        "generation_gate_passed": all(
            row["generation_gate_passed"] for row in conditions.values()
        ),
        "matcher_gate": {
            "status": "pending",
            "required": (
                "Corrected per-GT candidate matching and paired denominator "
                "validation"
            ),
        },
        "seed1_authorized_by_this_gate": False,
        "interpretation": (
            "A failed generation gate requires design review before any "
            "seed-1 generation. A passed generation gate still does not "
            "authorize API execution."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--actionable-quality",
        type=Path,
        default=(
            ROOT / "runs" / "ablation" / "actionable_only"
            / "batch_confirmatory_actionable_only_seed0_quality_summary.json"
        ),
    )
    parser.add_argument(
        "--identity-quality",
        type=Path,
        default=(
            ROOT / "runs" / "ablation" / "identity_only"
            / "batch_confirmatory_identity_only_seed0_quality_summary.json"
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = evaluate(
        json.loads(args.actionable_quality.read_text(encoding="utf-8")),
        json.loads(args.identity_quality.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "generation_gate_passed": result["generation_gate_passed"],
        "seed1_authorized_by_this_gate": (
            result["seed1_authorized_by_this_gate"]
        ),
        "output": str(args.output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
