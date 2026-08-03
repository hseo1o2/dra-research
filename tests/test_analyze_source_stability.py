from scripts.analyze_source_stability import (
    extract_search_sets,
    jaccard,
    normalize_url,
    summarize,
    task_rows,
)


def test_extract_search_sets_uses_attempted_queries_and_source_links() -> None:
    artifact = {
        "search_trace": [
            {
                "attempted": True,
                "query": "  Best   Hotels ",
                "sources": [
                    {"link": "HTTPS://Example.COM/a/#section"},
                    {"link": "https://example.com/b?x=1"},
                ],
            },
            {
                "attempted": False,
                "query": "Rejected query",
                "sources": [],
            },
        ]
    }

    result = extract_search_sets(artifact)

    assert result["queries"] == {"best hotels"}
    assert result["urls"] == {
        "https://example.com/a",
        "https://example.com/b?x=1",
    }


def test_url_normalization_and_jaccard() -> None:
    assert normalize_url("https://EXAMPLE.com/a/#x") == "https://example.com/a"
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_task_rows_contrast_within_and_between_overlap() -> None:
    artifacts = {}
    for taskid in (1, 2):
        for user, token in [("User1", "a"), ("User2", "b"), ("User3", "c")]:
            for seed in (0, 1):
                artifacts[(taskid, user, seed)] = {
                    "queries": {f"query-{token}"},
                    "urls": {f"https://example.com/{token}"},
                }

    rows = task_rows(artifacts)
    result = summarize(rows, repetitions=100, seed=3)

    assert len(rows) == 2
    assert result["metrics"]["queries"]["within_persona_cross_seed_mean"] == 1
    assert result["metrics"]["queries"]["between_persona_same_seed_mean"] == 0
    assert result["metrics"]["queries"]["within_minus_between"] == 1
    assert result["metrics"]["urls"]["task_bootstrap_ci95"] == [1, 1]
