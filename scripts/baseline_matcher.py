"""Non-LLM baselines for N-way persona attribution.

Baselines
---------
random    : uniform random over N candidates (analytical, no model)
bm25      : Okapi BM25 similarity between artifact text and persona text
embedding : cosine similarity via sentence-transformers

Usage
-----
# BM25 on confirmatory seed 0
python scripts/baseline_matcher.py \
  --batch-dir runs/confirmatory \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/baselines \
  --method bm25 --seed 0

# Embedding baseline
python scripts/baseline_matcher.py \
  --batch-dir runs/confirmatory \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/baselines \
  --method embedding --seed 0

# All methods at once
python scripts/baseline_matcher.py \
  --batch-dir runs/confirmatory \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/baselines \
  --method all --seed 0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random as _random
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

MANIFEST_PATH = ROOT / "manifest.json"
PERSONAS_PATH = ROOT / "data" / "pdr-bench" / "persona_data" / "personas_en.jsonl"
STAGES = ["plan", "search", "compress", "write"]
METHODS = ["random", "bm25", "embedding"]
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Artifact → text serializers (mirrors llm_matcher.py, simpler version)
# ---------------------------------------------------------------------------

def _artifact_to_text(artifacts: dict[str, Any], stage: str) -> str:
    if stage == "plan":
        return str(artifacts.get("research_brief", ""))
    if stage == "search":
        parts = []
        for item in artifacts.get("search_trace", []):
            if isinstance(item, dict):
                parts.append(item.get("query", ""))
                for r in item.get("results", [])[:3]:
                    if isinstance(r, dict):
                        parts.append(r.get("title", "") + " " + r.get("snippet", ""))
        return " ".join(parts)
    if stage == "compress":
        parts = []
        for item in artifacts.get("compressed_research", []):
            if isinstance(item, dict):
                # field name is 'compressed_research' inside the list item
                text = item.get("compressed_research") or item.get("summary") or ""
                parts.append(str(text))
        return " ".join(parts)
    if stage == "write":
        return str(artifacts.get("final_report", ""))
    return ""


def _persona_to_text(persona: dict[str, Any]) -> str:
    """Flatten persona dict to plain text for similarity matching."""
    parts: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)
        elif obj is not None:
            parts.append(str(obj))

    _walk(persona)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_personas() -> dict[str, Any]:
    personas: dict[str, Any] = {}
    with open(PERSONAS_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            personas[p["userid"]] = p
    return personas


def _lookup_run(run_id: str, manifest: dict[str, Any]) -> tuple[str, list[str]]:
    """Return (gt_userid, [candidate_userids]) for a run_id."""
    from scripts.candidate_protocol import lookup_pdr_candidates

    return lookup_pdr_candidates(run_id, manifest)


# ---------------------------------------------------------------------------
# BM25 baseline
# ---------------------------------------------------------------------------

def _bm25_predict(
    artifact_text: str,
    candidate_texts: dict[str, str],
) -> str:
    from rank_bm25 import BM25Okapi

    corpus = list(candidate_texts.values())
    userids = list(candidate_texts.keys())
    tokenized_corpus = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(artifact_text.lower().split())
    return userids[int(np.argmax(scores))]


# ---------------------------------------------------------------------------
# Embedding baseline (lazy-loaded model)
# ---------------------------------------------------------------------------

_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        try:
            _embed_model = SentenceTransformer(
                EMBEDDING_MODEL,
                local_files_only=True,
            )
        except OSError as exc:
            raise RuntimeError(
                f"Embedding model {EMBEDDING_MODEL!r} is not available in "
                "the local Hugging Face cache. Baseline execution is "
                "network-disabled; prefetch the model separately only with "
                "explicit approval."
            ) from exc
    return _embed_model


def _embedding_predict(
    artifact_text: str,
    candidate_texts: dict[str, str],
) -> str:
    model = _get_embed_model()
    userids = list(candidate_texts.keys())
    corpus = list(candidate_texts.values())
    all_texts = [artifact_text] + corpus
    embeddings = model.encode(all_texts, normalize_embeddings=True)
    artifact_vec = embeddings[0]
    persona_vecs = embeddings[1:]
    sims = persona_vecs @ artifact_vec
    return userids[int(np.argmax(sims))]


# ---------------------------------------------------------------------------
# Random baseline (deterministic per run_id)
# ---------------------------------------------------------------------------

def _random_predict(run_id: str, stage: str, candidates: list[str]) -> str:
    seed_material = f"random:{run_id}:{stage}".encode("utf-8")
    seed = int.from_bytes(
        hashlib.sha256(seed_material).digest()[:8],
        byteorder="big",
        signed=False,
    )
    rng = _random.Random(seed)
    return rng.choice(candidates)


# ---------------------------------------------------------------------------
# Core evaluation loop
# ---------------------------------------------------------------------------

def _run_baseline(
    method: str,
    artifact_paths: list[Path],
    manifest: dict[str, Any],
    personas: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    stage_correct: dict[str, int] = {s: 0 for s in STAGES}
    stage_total: dict[str, int] = {s: 0 for s in STAGES}
    all_rows: list[dict[str, Any]] = []

    for path in artifact_paths:
        run_id = path.name.replace("_artifacts.json", "")
        try:
            artifacts = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  SKIP {run_id}: {exc}")
            continue

        try:
            gt_userid, candidates = _lookup_run(run_id, manifest)
        except ValueError as exc:
            print(f"  SKIP {run_id}: {exc}")
            continue

        candidate_texts = {
            uid: _persona_to_text(personas.get(uid, {}))
            for uid in candidates
        }

        run_rows: list[dict[str, Any]] = []
        for stage in STAGES:
            artifact_text = _artifact_to_text(artifacts, stage)
            if not artifact_text.strip():
                continue

            if method == "random":
                pred = _random_predict(run_id, stage, candidates)
            elif method == "bm25":
                pred = _bm25_predict(artifact_text, candidate_texts)
            elif method == "embedding":
                pred = _embedding_predict(artifact_text, candidate_texts)
            else:
                raise ValueError(f"Unknown method: {method}")

            correct = pred == gt_userid
            stage_correct[stage] += int(correct)
            stage_total[stage] += 1
            run_rows.append({
                "run_id": run_id,
                "stage": stage,
                "gt_userid": gt_userid,
                "candidate_userids": candidates,
                "predicted_userid": pred,
                "correct": correct,
                "method": method,
            })
            mark = "✓" if correct else "✗"
            print(f"  {mark} {stage:10s}  pred={pred:8s}  gt={gt_userid}")

        print(f"[{run_id}]")
        all_rows.extend(run_rows)

        out_path = output_dir / f"{run_id}_{method}_match.json"
        out_path.write_text(json.dumps(run_rows, indent=2, ensure_ascii=False))

    # Accuracy summary
    acc: dict[str, float] = {}
    for stage in STAGES:
        t = stage_total[stage]
        acc[stage] = round(stage_correct[stage] / t, 4) if t else float("nan")

    valid_acc = [v for v in acc.values() if v == v]
    macro = round(sum(valid_acc) / len(valid_acc), 4) if valid_acc else float("nan")
    n = stage_total.get("plan", 0)
    chance = round(1.0 / 3, 4)

    print(f"\n--- {method.upper()} Attribution Accuracy ---")
    for stage in STAGES:
        v = acc[stage]
        bar = "█" * int(v * 20) if v == v else "—"
        print(f"  {stage:10s}  Acc={v:.3f}  {bar}")
    print(f"  macro      Acc={macro:.3f}  (chance={chance:.3f}, N={n})")

    summary = {
        "method": method,
        "accuracy": {**acc, "macro_avg": macro, "chance": chance, "n": n},
    }
    summary_path = output_dir / f"baseline_{method}_accuracy_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary → {summary_path}")
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Non-LLM persona attribution baselines")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--batch-dir", type=Path)
    src.add_argument("--run-id", type=str)
    parser.add_argument("--artifact-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--method", choices=METHODS + ["all"], default="all")
    parser.add_argument("--seed", type=int, default=None,
                        help="Filter artifacts by seed suffix")
    args = parser.parse_args()

    artifact_dir = args.artifact_dir or args.batch_dir
    if args.run_id:
        artifact_paths = [artifact_dir / f"{args.run_id}_artifacts.json"]
    else:
        artifact_paths = sorted(args.batch_dir.glob("*_artifacts.json"))
        if args.seed is not None:
            suffix = f"_seed{args.seed}_artifacts.json"
            artifact_paths = [p for p in artifact_paths if p.name.endswith(suffix)]

    manifest = _load_manifest()
    personas = _load_personas()

    methods = METHODS if args.method == "all" else [args.method]
    for method in methods:
        print(f"\n{'='*50}")
        print(f"Method: {method.upper()}  (N={len(artifact_paths)} artifacts)")
        print(f"{'='*50}")
        _run_baseline(method, artifact_paths, manifest, personas, args.output_dir)


if __name__ == "__main__":
    main()
