import json
from pathlib import Path

from scripts.build_candidate_sensitivity_plan import build_plan
from scripts.build_manifest import PDR_PERSONAS, PDR_QUERIES, load_jsonl


def test_real_manifest_candidate_sensitivity_extends_same_ranking() -> None:
    manifest = json.loads(
        Path("manifest.json").read_text(encoding="utf-8")
    )

    result = build_plan(
        manifest,
        load_jsonl(PDR_PERSONAS),
        load_jsonl(PDR_QUERIES),
    )

    assert result["external_api_calls"] == 0
    assert result["experiments"] == 60
    assert result["n3_manifest_exact_matches"] == 60
    assert not any(
        row["fallback_to_all_domains"] for row in result["rows"]
    )
    for row in result["rows"]:
        sets = row["candidate_sets"]
        assert sets["3"][:2] == sets["2"]
        assert sets["5"][:3] == sets["3"]
        assert len(set(sets["5"])) == 5
