from scripts import mask_identifiers


def test_mask_artifact_masks_v2_search_sources(monkeypatch):
    monkeypatch.setattr(
        mask_identifiers,
        "mask_text",
        lambda text: text.replace("Alice", "[MASKED]"),
    )
    artifact = {
        "search_trace": [{
            "query": "Alice travel",
            "sources": [{
                "title": "Alice guide",
                "snippet": "Advice for Alice",
                "query": "Alice travel",
            }],
        }],
    }
    masked = mask_identifiers.mask_artifact(artifact)
    call = masked["search_trace"][0]
    assert "Alice" not in call["query"]
    assert "Alice" not in call["sources"][0]["title"]
    assert "Alice" not in call["sources"][0]["snippet"]
    assert "Alice" not in call["sources"][0]["query"]


def test_identity_phrases_include_all_candidates() -> None:
    personas = {
        "User1": {
            "Basic Attributes": {
                "Identity Characteristics": {
                    "Name": "Alice Smith",
                    "Age": "22-25",
                    "Occupation": "Graduate student in Clinical Psychology",
                },
            },
        },
        "User2": {
            "Basic Attributes": {
                "Identity Characteristics": {
                    "Name": "Bob Jones",
                    "Occupation": "Mechanical automation engineer",
                },
            },
        },
    }
    phrases = mask_identifiers.identity_phrases_for_candidates(
        ["User1", "User2"],
        personas,
        {"Name", "Age", "Occupation"},
    )
    assert "Alice Smith" in phrases
    assert "22-25" in phrases
    assert "Graduate student in Clinical Psychology" in phrases
    assert "Mechanical automation engineer" in phrases


def test_mask_artifact_combines_identity_phrases_and_ner(monkeypatch) -> None:
    monkeypatch.setattr(
        mask_identifiers,
        "mask_text",
        lambda text: text.replace("London", "[MASKED]"),
    )
    artifact = {
        "research_brief": (
            "A graduate student in clinical psychology moved to London."
        ),
        "final_report": "Advice for a mechanical automation engineer.",
    }
    masked = mask_identifiers.mask_artifact(
        artifact,
        identity_phrases=[
            "Graduate student in Clinical Psychology",
            "Mechanical automation engineer",
        ],
        candidate_userids=["User1", "User2"],
    )
    assert "clinical psychology" not in masked["research_brief"].lower()
    assert "London" not in masked["research_brief"]
    assert "mechanical automation engineer" not in masked[
        "final_report"
    ].lower()
    assert masked["_masking"]["protocol"] == (
        mask_identifiers.IDENTITY_MASK_VERSION
    )
    assert masked["_masking"]["stage_replacements"]["plan"][
        "identity_phrase_replacements"
    ] == 1
