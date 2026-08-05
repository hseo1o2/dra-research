#!/usr/bin/env python3
"""Extended Search-mechanism analyses for REALM revision (no LLM calls).

Produces:
  - query genericization / diversity metrics
  - persona feature-bucket retention (identity / goals-ish / interests / decision)
  - matcher certainty proxy from free-text reasoning
  - second qualitative recovery vignette

Usage:
  open_deep_research/.venv/bin/python scripts/analyze_search_mechanism_extended.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
STRONG_RE = re.compile(
    r"\b(only|perfectly|clearly|unambiguously|definitively|strongest|"
    r"aligns perfectly|no other|exclusive|unmistakably|obviously|"
    r"most closely|best match|sole|decisively)\b",
    re.I,
)
HEDGE_RE = re.compile(
    r"\b(might|could|possibly|perhaps|unclear|ambiguous|either|"
    r"both|somewhat|partially|suggests?|appears?|seems?|"
    r"less clear|harder to|not definitive|no single)\b",
    re.I,
)
CAND_RE = re.compile(r"Candidate\s+[ABC]", re.I)

# Surface generic retrieval patterns (topic catalogs, not persona framing).
GENERIC_PHRASES = [
    "best books",
    "best practices",
    "how to",
    "what is",
    "overview of",
    "introduction to",
    "top 10",
    "isbn",
    "pdf",
    "course",
    "tutorial",
    "guide to",
    "list of",
    "vs ",
    "versus",
    "review of",
    "definition of",
    "examples of",
    "methods for",
    "strategies for",
    "techniques for",
    "workbook",
    "textbook",
    "syllabus",
]

# Map persona sections → analysis buckets (reviewer-facing labels).
FEATURE_BUCKETS: dict[str, list[str]] = {
    "identity": [
        "Basic Attributes.Identity Characteristics",
        "Basic Attributes.Family Status",
        "Basic Attributes.Long-term Spatial Characteristics",
    ],
    "decision_style": [
        "Behavioral Characteristics.Personality Traits",
        "Behavioral Characteristics.Environment.Time",
    ],
    "interests": [
        "Behavioral Characteristics.Preferences and Interests",
        "Behavioral Characteristics.Online Usage Habits",
        "Behavioral Characteristics.Offline Long-term Behavior",
    ],
    "goals_constraints": [
        "Health Status",
        "Financial Information",
    ],
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "to", "for", "is", "are", "was", "were",
    "he", "she", "they", "his", "her", "their", "it", "this", "that", "with", "on",
    "at", "by", "from", "as", "has", "have", "had", "not", "but", "also", "been",
    "which", "who", "when", "where", "what", "how", "its", "be", "do", "does", "did",
    "i", "my", "me", "we", "our", "you", "your", "can", "will", "would", "should",
    "may", "into", "than", "then", "so", "if", "about", "more", "most", "other",
}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 2]


def entropy(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    n = len(tokens)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def type_token_ratio(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def flatten_text(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (int, float, bool)):
        return str(obj)
    if isinstance(obj, list):
        return " ".join(flatten_text(x) for x in obj)
    if isinstance(obj, dict):
        return " ".join(flatten_text(v) for v in obj.values())
    return str(obj)


def load_personas(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        out[str(p["userid"])] = p
    return out


def bucket_tokens(persona: dict) -> dict[str, set[str]]:
    buckets: dict[str, set[str]] = {}
    for name, paths in FEATURE_BUCKETS.items():
        toks: set[str] = set()
        for path in paths:
            node = get_path(persona, path)
            toks.update(tokenize(flatten_text(node)))
        buckets[name] = toks
    return buckets


def retention(src: set[str], text: str) -> float:
    if not src:
        return 0.0
    tgt = set(tokenize(text))
    return len(src & tgt) / len(src)


def load_match_map(match_dir: Path) -> dict[str, dict[str, dict]]:
    """run_id -> stage -> match record."""
    out: dict[str, dict[str, dict]] = {}
    for path in sorted(match_dir.glob("pilot_*_match.json")):
        items = json.loads(path.read_text(encoding="utf-8"))
        if not items:
            continue
        run_id = items[0]["run_id"]
        out[run_id] = {it["stage"]: it for it in items}
    return out


def extract_queries(art: dict) -> list[str]:
    queries: list[str] = []
    for entry in art.get("search_trace") or []:
        q = entry.get("query")
        if isinstance(q, str) and q.strip():
            queries.append(q.strip())
    return queries


def extract_urls(art: dict) -> list[str]:
    urls: list[str] = []
    for entry in art.get("search_trace") or []:
        for src in entry.get("sources") or []:
            link = src.get("link") or src.get("url")
            if isinstance(link, str) and link:
                urls.append(link)
    return urls


def url_categories(urls: list[str]) -> dict[str, float]:
    cats = Counter()
    for u in urls:
        host = urlparse(u).netloc.lower()
        if not host:
            cats["unknown"] += 1
            continue
        if any(x in host for x in ("amazon", "dangdang", "book", "goodreads", "isbn")):
            cats["retail_books"] += 1
        elif any(x in host for x in ("youtube", "bilibili", "vimeo")):
            cats["video"] += 1
        elif any(x in host for x in ("wikipedia", "wiki")):
            cats["encyclopedia"] += 1
        elif any(x in host for x in ("edu", "ac.", "arxiv", "springer", "ieee", "acm.org", "nih.gov", "pubmed")):
            cats["academic"] += 1
        elif any(x in host for x in ("reddit", "zhihu", "quora", "stackoverflow")):
            cats["forum"] += 1
        elif any(x in host for x in ("coursera", "udemy", "edx", "skillshare", "khan")):
            cats["course_platform"] += 1
        elif any(x in host for x in ("gov", "who.int", "cdc.gov")):
            cats["gov"] += 1
        elif any(x in host for x in ("medium.com", "blog", "substack")):
            cats["blog"] += 1
        else:
            cats["other_web"] += 1
    n = sum(cats.values()) or 1
    return {k: v / n for k, v in cats.items()}


def generic_hit_rate(queries: list[str]) -> float:
    if not queries:
        return 0.0
    hits = 0
    for q in queries:
        ql = q.lower()
        if any(p in ql for p in GENERIC_PHRASES):
            hits += 1
    return hits / len(queries)


def certainty_proxy(reasoning: str) -> dict[str, float]:
    strong = len(STRONG_RE.findall(reasoning))
    hedge = len(HEDGE_RE.findall(reasoning))
    cands = len(set(CAND_RE.findall(reasoning)))
    # Higher = more exclusive/certain.
    score = strong - 0.5 * hedge
    if cands <= 1:
        score += 0.5
    return {
        "strong_count": float(strong),
        "hedge_count": float(hedge),
        "cand_mentions": float(cands),
        "certainty_score": float(score),
        "has_strong": 1.0 if strong > 0 else 0.0,
        "has_hedge": 1.0 if hedge > 0 else 0.0,
    }


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def analyze(
    artifacts_dir: Path,
    match_dir: Path,
    personas_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    personas = load_personas(personas_path)
    matches = load_match_map(match_dir)
    rows: list[dict[str, Any]] = []

    art_paths = sorted(artifacts_dir.glob("pilot_*_artifacts.json"))
    for ap in art_paths:
        art = json.loads(ap.read_text(encoding="utf-8"))
        run_id = art["run_id"]
        gt = str(art["execution_config"]["gt_userid"])
        persona = personas.get(gt)
        if persona is None:
            continue
        m = matches.get(run_id)
        if not m or "search" not in m:
            continue

        brief = art.get("research_brief") or ""
        queries = extract_queries(art)
        qtext = " ".join(queries)
        urls = extract_urls(art)
        url_cat = url_categories(urls)
        q_tokens = tokenize(qtext)
        brief_tokens = tokenize(brief)
        buckets = bucket_tokens(persona)

        search_correct = bool(m["search"]["correct"])
        plan_correct = bool(m.get("plan", {}).get("correct", False))
        write_correct = bool(m.get("write", {}).get("correct", False))

        row: dict[str, Any] = {
            "run_id": run_id,
            "gt": gt,
            "domain": art.get("execution_config", {}).get("domain")
            or _domain_from_summary(artifacts_dir, run_id),
            "search_correct": search_correct,
            "plan_correct": plan_correct,
            "write_correct": write_correct,
            "n_queries": len(queries),
            "n_unique_queries": len(set(queries)),
            "query_unique_ratio": (len(set(queries)) / len(queries)) if queries else 0.0,
            "mean_query_chars": mean([len(q) for q in queries]),
            "unique_query_tokens": float(len(set(q_tokens))),
            "query_token_count": float(len(q_tokens)),
            "query_ttr": type_token_ratio(q_tokens),
            "query_entropy": entropy(q_tokens),
            "brief_entropy": entropy(brief_tokens),
            "generic_hit_rate": generic_hit_rate(queries),
            "n_urls": len(urls),
            "n_unique_hosts": len({urlparse(u).netloc.lower() for u in urls if u}),
            "url_cat_entropy": entropy(
                [c for c, frac in url_cat.items() for _ in range(max(1, int(round(frac * 100))))]
            )
            if url_cat
            else 0.0,
            "url_retail_books_frac": url_cat.get("retail_books", 0.0),
            "url_academic_frac": url_cat.get("academic", 0.0),
            "url_course_frac": url_cat.get("course_platform", 0.0),
            "url_other_frac": url_cat.get("other_web", 0.0),
        }

        for bname, btoks in buckets.items():
            row[f"ret_{bname}_brief"] = retention(btoks, brief)
            row[f"ret_{bname}_query"] = retention(btoks, qtext)
            row[f"drop_{bname}"] = row[f"ret_{bname}_brief"] - row[f"ret_{bname}_query"]
            row[f"n_{bname}_tokens"] = float(len(btoks))

        # Matcher certainty by stage
        for stage in ("plan", "search", "compress", "write"):
            if stage not in m:
                continue
            cert = certainty_proxy(m[stage].get("reasoning") or "")
            for k, v in cert.items():
                row[f"{stage}_{k}"] = v
            row[f"{stage}_correct"] = 1.0 if m[stage]["correct"] else 0.0

        rows.append(row)

    # Summaries
    def subset(pred) -> list[dict[str, Any]]:
        return [r for r in rows if pred(r)]

    sc = subset(lambda r: r["search_correct"])
    sw = subset(lambda r: not r["search_correct"])

    metric_keys = [
        "n_queries",
        "n_unique_queries",
        "query_unique_ratio",
        "mean_query_chars",
        "unique_query_tokens",
        "query_ttr",
        "query_entropy",
        "generic_hit_rate",
        "n_unique_hosts",
        "url_retail_books_frac",
        "url_academic_frac",
        "url_course_frac",
    ]
    feature_keys = []
    for b in FEATURE_BUCKETS:
        feature_keys += [f"ret_{b}_brief", f"ret_{b}_query", f"drop_{b}"]

    certainty_keys = []
    for st in ("plan", "search", "compress", "write"):
        certainty_keys += [
            f"{st}_certainty_score",
            f"{st}_has_strong",
            f"{st}_has_hedge",
            f"{st}_cand_mentions",
        ]

    def summarize(rs: list[dict[str, Any]], keys: list[str]) -> dict[str, float]:
        return {k: mean([float(r[k]) for r in rs if k in r]) for k in keys}

    summary: dict[str, Any] = {
        "n": len(rows),
        "n_search_correct": len(sc),
        "n_search_wrong": len(sw),
        "overall": summarize(rows, metric_keys + feature_keys),
        "search_correct": summarize(sc, metric_keys + feature_keys),
        "search_wrong": summarize(sw, metric_keys + feature_keys),
        "certainty_by_stage": {
            st: {
                "certainty_score": mean([float(r[f"{st}_certainty_score"]) for r in rows]),
                "has_strong": mean([float(r[f"{st}_has_strong"]) for r in rows]),
                "has_hedge": mean([float(r[f"{st}_has_hedge"]) for r in rows]),
                "cand_mentions": mean([float(r[f"{st}_cand_mentions"]) for r in rows]),
                "acc": mean([float(r[f"{st}_correct"]) for r in rows]),
            }
            for st in ("plan", "search", "compress", "write")
        },
        "feature_retention_overall": {
            b: {
                "brief": mean([float(r[f"ret_{b}_brief"]) for r in rows]),
                "query": mean([float(r[f"ret_{b}_query"]) for r in rows]),
                "drop": mean([float(r[f"drop_{b}"]) for r in rows]),
            }
            for b in FEATURE_BUCKETS
        },
        "deltas_search_correct_minus_wrong": {
            k: summarize(sc, [k])[k] - summarize(sw, [k])[k] for k in metric_keys + feature_keys
        },
    }

    # Qualitative second case: recovery with high generic hit or high identity drop
    recovery = [
        r
        for r in rows
        if r["plan_correct"] and (not r["search_correct"]) and r["write_correct"]
    ]
    recovery_sorted = sorted(
        recovery,
        key=lambda r: (r["generic_hit_rate"], r.get("drop_identity", 0.0), r["mean_query_chars"]),
        reverse=True,
    )
    vignettes = []
    for r in recovery_sorted[:5]:
        ap = artifacts_dir / f"{r['run_id']}_artifacts.json"
        art = json.loads(ap.read_text(encoding="utf-8"))
        qs = extract_queries(art)[:6]
        vignettes.append(
            {
                "run_id": r["run_id"],
                "gt": r["gt"],
                "generic_hit_rate": r["generic_hit_rate"],
                "drop_identity": r.get("drop_identity", 0.0),
                "drop_decision_style": r.get("drop_decision_style", 0.0),
                "drop_interests": r.get("drop_interests", 0.0),
                "brief_excerpt": (art.get("research_brief") or "")[:280],
                "sample_queries": qs,
                "search_pred": matches[r["run_id"]]["search"]["predicted_userid"],
                "write_pred": matches[r["run_id"]]["write"]["predicted_userid"],
            }
        )
    summary["qualitative_candidates"] = vignettes
    summary["notes"] = [
        "Matcher has no calibrated confidence field; certainty_score is a free-text proxy "
        "(strong exclusive language − hedge language).",
        "Feature buckets are section-level lexical retention, not causal ablation.",
        "Generic phrases are a fixed surface list for topic-catalog query patterns.",
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "search_mechanism_extended_rows.csv"
    if rows:
        keys = list(rows[0].keys())
        with rows_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    summary_path = out_dir / "search_mechanism_extended_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {rows_path}")
    print(f"Wrote {summary_path}")
    print(json.dumps({
        "n": summary["n"],
        "overall_generic": summary["overall"]["generic_hit_rate"],
        "sc_generic": summary["search_correct"]["generic_hit_rate"],
        "sw_generic": summary["search_wrong"]["generic_hit_rate"],
        "feature_retention": summary["feature_retention_overall"],
        "certainty": summary["certainty_by_stage"],
        "top_vignette": vignettes[0]["run_id"] if vignettes else None,
    }, indent=2))
    return summary


def _domain_from_summary(artifacts_dir: Path, run_id: str) -> str:
    sp = artifacts_dir / f"{run_id}_summary.json"
    if sp.exists():
        try:
            return str(json.loads(sp.read_text(encoding="utf-8")).get("domain") or "")
        except json.JSONDecodeError:
            return ""
    return ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--artifacts-dir",
        type=Path,
        default=ROOT / "runs" / "confirmatory",
    )
    p.add_argument(
        "--match-dir",
        type=Path,
        default=ROOT / "runs" / "confirmatory" / "matches_hardneg_v1",
    )
    p.add_argument(
        "--personas",
        type=Path,
        default=ROOT / "data" / "pdr-bench" / "persona_data" / "personas_en.jsonl",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "runs" / "confirmatory" / "analysis_search_mechanism_extended",
    )
    args = p.parse_args()
    analyze(args.artifacts_dir, args.match_dir, args.personas, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
