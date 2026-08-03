"""Construct frozen leaf-key persona profiles for generation ablations."""

from __future__ import annotations

from typing import Any

CONDITIONS = (
    "full",
    "actionable_only",
    "identity_only",
    "shuffled_actionable",
)


def _project_value(
    value: Any,
    identity_leaf_keys: set[str],
    keep_identity: bool,
) -> Any:
    if not isinstance(value, dict):
        return value
    projected: dict[str, Any] = {}
    for key, child in value.items():
        if isinstance(child, dict):
            nested = _project_value(
                child, identity_leaf_keys, keep_identity
            )
            if nested:
                projected[key] = nested
            continue
        is_identity = key in identity_leaf_keys
        if is_identity == keep_identity:
            projected[key] = child
    return projected


def project_persona(
    persona: dict[str, Any],
    condition: str,
    identity_leaf_keys: set[str],
) -> dict[str, Any]:
    """Return the full or frozen leaf-key projection of one persona."""
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown persona condition: {condition}")
    if condition == "full":
        return dict(persona)
    if condition == "shuffled_actionable":
        raise ValueError(
            "shuffled_actionable requires separate identity-shell and "
            "actionable-donor personas; use compose_shuffled_actionable()"
        )
    keep_identity = condition == "identity_only"
    projected = _project_value(
        {key: value for key, value in persona.items() if key != "userid"},
        identity_leaf_keys,
        keep_identity,
    )
    if not projected:
        raise ValueError(
            f"{condition} projection is empty for {persona.get('userid')}"
        )
    return {"userid": persona.get("userid"), **projected}


def actionable_donor_userid(
    identity_shell_userid: str,
    group_userids: list[str],
) -> str:
    """Return the next persona in the frozen cyclic donor permutation."""
    if len(group_userids) < 2 or len(set(group_userids)) != len(group_userids):
        raise ValueError("Donor group must contain distinct personas")
    try:
        shell_index = group_userids.index(identity_shell_userid)
    except ValueError as exc:
        raise ValueError(
            f"Identity shell {identity_shell_userid} not in donor group"
        ) from exc
    return group_userids[(shell_index + 1) % len(group_userids)]


def _merge_disjoint(left: Any, right: Any, path: str = "") -> Any:
    if not isinstance(left, dict) or not isinstance(right, dict):
        if left == right:
            return left
        raise ValueError(f"Conflicting shuffled profile leaves at {path}")
    merged: dict[str, Any] = {}
    for key in left.keys() | right.keys():
        child_path = f"{path}.{key}" if path else key
        if key in left and key in right:
            merged[key] = _merge_disjoint(
                left[key], right[key], child_path
            )
        elif key in left:
            merged[key] = left[key]
        else:
            merged[key] = right[key]
    return merged


def compose_shuffled_actionable(
    identity_shell: dict[str, Any],
    actionable_donor: dict[str, Any],
    identity_leaf_keys: set[str],
) -> dict[str, Any]:
    """Combine shell identity leaves with another persona's actionable leaves."""
    shell_profile = project_persona(
        identity_shell, "identity_only", identity_leaf_keys
    )
    donor_profile = project_persona(
        actionable_donor, "actionable_only", identity_leaf_keys
    )
    shell_body = {
        key: value for key, value in shell_profile.items() if key != "userid"
    }
    donor_body = {
        key: value for key, value in donor_profile.items() if key != "userid"
    }
    merged = _merge_disjoint(shell_body, donor_body)
    return {"userid": identity_shell.get("userid"), **merged}


def leaf_count(value: Any) -> int:
    if isinstance(value, dict):
        return sum(leaf_count(child) for child in value.values())
    return 1
