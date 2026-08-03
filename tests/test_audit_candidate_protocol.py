import json
from pathlib import Path

from scripts.audit_candidate_protocol import audit


def test_audit_detects_candidate_set_mismatch(tmp_path: Path) -> None:
    manifest = {
        "pdr_bench": {
            "dev": [],
            "confirmatory": [{
                "taskid": 2,
                "personas_n3": ["User2", "User6", "User7"],
                "experiments": [{
                    "gt_userid": "User2",
                    "attribution_candidate_set_n3": [
                        "User2", "User1", "User7"
                    ],
                }],
            }],
        }
    }
    records = [{
        "run_id": "pilot_task2_User2_seed0",
        "stage": stage,
        "candidate_userids": ["User2", "User6", "User7"],
    } for stage in ("plan", "search", "compress", "write")]
    (tmp_path / "run_match.json").write_text(
        json.dumps(records), encoding="utf-8"
    )

    result = audit(manifest, tmp_path)

    assert result["passed"] is False
    assert result["mismatching_candidate_sets"] == 1
