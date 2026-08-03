import json
from pathlib import Path

from scripts.candidate_protocol import lookup_pdr_candidates


def _manifest() -> dict:
    return json.loads(Path("manifest.json").read_text(encoding="utf-8"))


def test_reference_condition_uses_per_gt_hard_negative_candidates() -> None:
    manifest = _manifest()

    gt, candidates = lookup_pdr_candidates(
        "pilot_task2_User2_seed0", manifest
    )

    assert gt == "User2"
    assert candidates == ["User2", "User1", "User7"]
    task = next(
        row for row in manifest["pdr_bench"]["confirmatory"]
        if row["taskid"] == 2
    )
    assert candidates != task["personas_n3"]


def test_profile_ablation_uses_same_hard_negative_candidates() -> None:
    manifest = _manifest()

    full = lookup_pdr_candidates(
        "pilot_task2_User2_seed0", manifest
    )[1]
    actionable = lookup_pdr_candidates(
        "ablation_actionable_only_task2_User2_seed0", manifest
    )[1]
    identity = lookup_pdr_candidates(
        "ablation_identity_only_task2_User2_seed0", manifest
    )[1]

    assert full == actionable == identity


def test_shuffled_condition_contains_shell_and_cyclic_donor() -> None:
    manifest = _manifest()

    gt, candidates = lookup_pdr_candidates(
        "ablation_shuffled_actionable_task2_User2_seed0", manifest
    )

    assert gt == "User2"
    assert candidates == ["User2", "User6", "User7"]
    assert "User6" in candidates
