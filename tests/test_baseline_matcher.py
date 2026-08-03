import sys
from types import SimpleNamespace

import scripts.baseline_matcher as baseline_matcher
from scripts.baseline_matcher import _random_predict


def test_random_baseline_is_deterministic():
    candidates = ["User1", "User2", "User3"]
    first = _random_predict("pilot_task1_User1_seed0", "search", candidates)
    second = _random_predict("pilot_task1_User1_seed0", "search", candidates)
    assert first == second
    assert first in candidates


def test_embedding_model_load_is_local_only(monkeypatch):
    calls = []
    sentinel = object()

    def fake_constructor(model_name, **kwargs):
        calls.append((model_name, kwargs))
        return sentinel

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=fake_constructor),
    )
    monkeypatch.setattr(baseline_matcher, "_embed_model", None)

    assert baseline_matcher._get_embed_model() is sentinel
    assert calls == [(
        baseline_matcher.EMBEDDING_MODEL,
        {"local_files_only": True},
    )]
