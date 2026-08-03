from scripts.build_provenance import RUN_DIRS, TRACKED_INPUTS


def test_provenance_includes_ablation_and_candidate_plans() -> None:
    assert any(path.parts[-2:] == ("runs", "ablation") for path in RUN_DIRS)
    names = {path.name for path in TRACKED_INPUTS}
    assert "candidate_sensitivity_plan.json" in names
    assert "hardneg_rerun_estimate.json" in names
