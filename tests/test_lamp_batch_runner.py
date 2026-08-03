import json
from pathlib import Path

from scripts.lamp_batch_runner import (
    DEFAULT_DATA_ROOT,
    DEFAULT_MANIFEST,
    build_user_message,
    iter_experiments,
    main,
)


def test_lamp_plan_has_90_unique_runs():
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    rows = iter_experiments(manifest, DEFAULT_DATA_ROOT, seeds=(0, 1))
    assert len(rows) == 90
    assert len({row["run_id"] for row in rows}) == 90
    assert sum(row["is_gt_profile"] for row in rows) == 30
    assert {row["generation_seed"] for row in rows} == {0, 1}
    assert len({row["query_index"] for row in rows}) == 15


def test_lamp_prompt_excludes_target_rubric_and_narrative():
    prompt = build_user_message(
        "What should I research?",
        [{"id": "p1", "text": "Prior question", "category": "history"}],
    )
    assert "What should I research?" in prompt
    assert "Prior question" in prompt
    assert "rubric_aspects" not in prompt
    assert "narrative" not in prompt


def test_lamp_plan_only_writes_network_free_plan(tmp_path: Path, capsys):
    plan_path = tmp_path / "plan.json"
    rc = main(["--seed", "all", "--plan-out", str(plan_path)])
    assert rc == 0
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "plan_only"
    assert payload["external_api_calls"] == 0
    assert payload["expected_runs"] == 90
    assert "Plan only. External API calls: 0" in capsys.readouterr().out


def test_lamp_execute_is_guarded_before_credentials(tmp_path: Path, capsys):
    rc = main(
        [
            "--seed",
            "0",
            "--plan-out",
            str(tmp_path / "plan.json"),
            "--execute",
        ]
    )
    assert rc == 1
    assert "--acknowledge-pdr-finished" in capsys.readouterr().err
