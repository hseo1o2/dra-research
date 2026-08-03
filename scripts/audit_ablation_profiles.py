"""Build a network-free audit of frozen generation-ablation profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dry_run import _build_user_message, _load_persona
from scripts.persona_ablation import (
    actionable_donor_userid,
    compose_shuffled_actionable,
    leaf_count,
    project_persona,
)

DEFAULT_OUTPUT = ROOT / "runs" / "ablation" / "profile_audit.json"


def _leaf_keys(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    keys: set[str] = set()
    for key, child in value.items():
        if isinstance(child, dict):
            keys.update(_leaf_keys(child))
        else:
            keys.add(key)
    return keys


def _body(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in profile.items() if key != "userid"
    }


def _sha256_json(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_audit(manifest: dict[str, Any]) -> dict[str, Any]:
    identity_keys = set(
        manifest["actionable_identity_split"]["identity_leaf_keys"]
    )
    taskids = set(manifest["pdr_bench"]["ablation_subset"]["taskids"])
    tasks = [
        row for row in manifest["pdr_bench"]["confirmatory"]
        if row["taskid"] in taskids
    ]
    rows: list[dict[str, Any]] = []
    for task in tasks:
        for experiment in task["experiments"]:
            userid = experiment["gt_userid"]
            persona = _load_persona(userid)
            for condition in ("actionable_only", "identity_only"):
                profile = project_persona(persona, condition, identity_keys)
                profile_keys = _leaf_keys(
                    {key: value for key, value in profile.items()
                     if key != "userid"}
                )
                prompt = _build_user_message(
                    task, {"query": task["task"]}, profile
                )
                rows.append({
                    "condition": condition,
                    "taskid": task["taskid"],
                    "domain": task["domain"],
                    "userid": userid,
                    "profile_leaf_count": leaf_count(profile) - 1,
                    "profile_chars": len(json.dumps(
                        profile, ensure_ascii=False, sort_keys=True
                    )),
                    "prompt_chars": len(prompt),
                    "prompt_sha256": hashlib.sha256(
                        prompt.encode("utf-8")
                    ).hexdigest(),
                    "identity_keys_present": sorted(
                        profile_keys & identity_keys
                    ),
                    "non_identity_keys_present": sorted(
                        profile_keys - identity_keys
                    ),
                    "embedded_full_persona_marker_count": (
                        prompt.count("User Persona:")
                    ),
                })
            donor_userid = actionable_donor_userid(
                userid, list(task["personas_n3"])
            )
            donor_persona = _load_persona(donor_userid)
            shuffled = compose_shuffled_actionable(
                persona, donor_persona, identity_keys
            )
            shuffled_identity = project_persona(
                shuffled, "identity_only", identity_keys
            )
            shuffled_actionable = project_persona(
                shuffled, "actionable_only", identity_keys
            )
            expected_identity = project_persona(
                persona, "identity_only", identity_keys
            )
            expected_actionable = project_persona(
                donor_persona, "actionable_only", identity_keys
            )
            prompt = _build_user_message(
                task, {"query": task["task"]}, shuffled
            )
            rows.append({
                "condition": "shuffled_actionable",
                "taskid": task["taskid"],
                "domain": task["domain"],
                "userid": userid,
                "identity_shell_userid": userid,
                "actionable_donor_userid": donor_userid,
                "donor_mapping": "cyclic-next-in-frozen-personas_n3",
                "profile_leaf_count": leaf_count(shuffled) - 1,
                "profile_chars": len(json.dumps(
                    shuffled, ensure_ascii=False, sort_keys=True
                )),
                "prompt_chars": len(prompt),
                "prompt_sha256": hashlib.sha256(
                    prompt.encode("utf-8")
                ).hexdigest(),
                "identity_projection_matches_shell": (
                    _sha256_json(_body(shuffled_identity))
                    == _sha256_json(_body(expected_identity))
                ),
                "actionable_projection_matches_donor": (
                    _sha256_json(_body(shuffled_actionable))
                    == _sha256_json(_body(expected_actionable))
                ),
                "embedded_full_persona_marker_count": (
                    prompt.count("User Persona:")
                ),
            })
    violations: list[str] = []
    for row in rows:
        if row["embedded_full_persona_marker_count"] != 1:
            violations.append(
                f"persona marker count: {row['condition']} "
                f"task{row['taskid']} {row['userid']}"
            )
        if row["condition"] == "actionable_only" and row[
            "identity_keys_present"
        ]:
            violations.append(
                f"identity leakage: task{row['taskid']} {row['userid']}"
            )
        if row["condition"] == "identity_only" and row[
            "non_identity_keys_present"
        ]:
            violations.append(
                f"actionable leakage: task{row['taskid']} {row['userid']}"
            )
        if row["profile_leaf_count"] == 0:
            violations.append(
                f"empty profile: {row['condition']} "
                f"task{row['taskid']} {row['userid']}"
            )
        if row["condition"] == "shuffled_actionable":
            if row["identity_shell_userid"] == row[
                "actionable_donor_userid"
            ]:
                violations.append(
                    f"self donor: task{row['taskid']} {row['userid']}"
                )
            if not row["identity_projection_matches_shell"]:
                violations.append(
                    f"identity projection mismatch: "
                    f"task{row['taskid']} {row['userid']}"
                )
            if not row["actionable_projection_matches_donor"]:
                violations.append(
                    f"actionable projection mismatch: "
                    f"task{row['taskid']} {row['userid']}"
                )
    return {
        "schema_version": 1,
        "external_api_calls": 0,
        "split_version": manifest["actionable_identity_split"]["version"],
        "identity_leaf_keys": sorted(identity_keys),
        "conditions": [
            "actionable_only",
            "identity_only",
            "shuffled_actionable",
        ],
        "reports_per_condition": len(rows) // 3,
        "reports_per_seed": len(rows),
        "rows": rows,
        "violations": violations,
        "passed": not violations,
        "claim_boundary": (
            "Profiles operationalize the frozen leaf-key split. This audit "
            "does not adjudicate within-leaf semantic ambiguity."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "manifest.json"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    audit = build_audit(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({
        "passed": audit["passed"],
        "reports_per_seed": audit["reports_per_seed"],
        "rows": len(audit["rows"]),
        "violations": len(audit["violations"]),
        "output": str(args.output),
    }, indent=2))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
