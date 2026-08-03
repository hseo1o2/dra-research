from scripts.analyze_sigir_sanity import (
    requested_word_range,
    text_metrics,
    token_jaccard,
)


def test_requested_word_range_accepts_en_dash_and_commas():
    assert requested_word_range("Write a 1,800 – 2,200-word report.") == (
        1800,
        2200,
    )


def test_text_metrics_are_deterministic():
    metrics = text_metrics("# Title\n\nFirst paragraph.\n\n- One\n- Two\n")
    assert metrics["words"] == 5
    assert metrics["paragraphs"] == 3
    assert metrics["markdown_headings"] == 1
    assert metrics["bullet_lines"] == 2


def test_token_jaccard_is_bounded():
    assert token_jaccard("alpha beta", "beta gamma") == 0.3333
    assert token_jaccard("", "") == 0.0
