from scripts.persona_ablation import (
    actionable_donor_userid,
    compose_shuffled_actionable,
    leaf_count,
    project_persona,
)


PERSONA = {
    "userid": "User1",
    "Basic Attributes": {
        "Identity Characteristics": {
            "Name": "Alice",
            "Occupation": "Engineer",
        }
    },
    "Preferences and Interests": {
        "Lifestyle": {
            "Budget Preference": "Cost conscious",
            "Travel Style": "Self guided",
        }
    },
}


def test_actionable_only_drops_identity_leaves():
    profile = project_persona(
        PERSONA, "actionable_only", {"Name", "Occupation"}
    )
    text = str(profile)
    assert "Alice" not in text
    assert "Engineer" not in text
    assert "Cost conscious" in text
    assert leaf_count(profile) == 3  # userid + two actionable leaves


def test_identity_only_drops_actionable_leaves():
    profile = project_persona(
        PERSONA, "identity_only", {"Name", "Occupation"}
    )
    text = str(profile)
    assert "Alice" in text
    assert "Engineer" in text
    assert "Cost conscious" not in text


def test_shuffled_actionable_combines_shell_identity_and_donor_preferences():
    donor = {
        **PERSONA,
        "userid": "User2",
        "Basic Attributes": {
            "Identity Characteristics": {
                "Name": "Bob",
                "Occupation": "Designer",
            }
        },
        "Preferences and Interests": {
            "Lifestyle": {
                "Budget Preference": "Premium",
                "Travel Style": "Guided",
            }
        },
    }

    profile = compose_shuffled_actionable(
        PERSONA, donor, {"Name", "Occupation"}
    )
    text = str(profile)

    assert profile["userid"] == "User1"
    assert "Alice" in text
    assert "Engineer" in text
    assert "Premium" in text
    assert "Guided" in text
    assert "Bob" not in text
    assert "Cost conscious" not in text


def test_donor_mapping_is_frozen_cyclic_permutation():
    group = ["User2", "User6", "User7"]
    assert actionable_donor_userid("User2", group) == "User6"
    assert actionable_donor_userid("User6", group) == "User7"
    assert actionable_donor_userid("User7", group) == "User2"


def test_batch_runner_ablation_uses_frozen_subset():
    import json
    from pathlib import Path

    from scripts.batch_runner import _iter_experiments, _run_id

    manifest = json.loads(Path("manifest.json").read_text())
    rows = _iter_experiments(
        manifest, "confirmatory", 0, "actionable_only"
    )
    assert len(rows) == 15
    assert {row[0]["taskid"] for row in rows} == {2, 7, 12, 22, 27}
    assert _run_id(2, "User2", 0, "actionable_only") == (
        "ablation_actionable_only_task2_User2_seed0"
    )
    shuffled = _iter_experiments(
        manifest, "confirmatory", 0, "shuffled_actionable"
    )
    assert len(shuffled) == 15
    assert _run_id(2, "User2", 0, "shuffled_actionable") == (
        "ablation_shuffled_actionable_task2_User2_seed0"
    )
