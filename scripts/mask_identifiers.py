"""Post-processing shortcut control: identifier masking via spaCy NER.

Replaces PERSON / ORG / GPE / NORP / FAC entity spans in every text field
of a DRA artifact with the placeholder [MASKED].  The masked artifact is
written to <output_dir>/<run_id>_masked_artifacts.json and can be fed
directly to llm_matcher.py or baseline_matcher.py.

Usage
-----
# Mask all seed-0 confirmatory artifacts
python scripts/mask_identifiers.py \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/masked \
  --seed 0

# Single run
python scripts/mask_identifiers.py \
  --run-id pilot_task3_User10_seed0 \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/masked
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import spacy

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MASK_TOKEN = "[MASKED]"
MASK_LABELS = {"PERSON", "ORG", "GPE", "NORP", "FAC"}

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def mask_text(text: str) -> str:
    if not text or not text.strip():
        return text
    nlp = _get_nlp()
    # spaCy has a default max_length; chunk large texts
    max_len = 900_000
    if len(text) <= max_len:
        doc = nlp(text)
        chunks = [doc]
    else:
        # process in chunks, reassemble
        parts = [text[i:i+max_len] for i in range(0, len(text), max_len)]
        chunks = [nlp(p) for p in parts]

    result_parts: list[str] = []
    for doc in chunks:
        offset = 0
        buf: list[str] = []
        for ent in doc.ents:
            if ent.label_ in MASK_LABELS:
                buf.append(doc.text[offset:ent.start_char])
                buf.append(MASK_TOKEN)
                offset = ent.end_char
        buf.append(doc.text[offset:])
        result_parts.append("".join(buf))
    return "".join(result_parts)


def mask_artifact(artifacts: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of artifacts with identifiers masked."""
    masked = dict(artifacts)

    # plan: research_brief
    if "research_brief" in masked:
        masked["research_brief"] = mask_text(str(masked["research_brief"]))

    # search: query strings + result snippets/titles
    if "search_trace" in masked:
        new_trace = []
        for item in masked["search_trace"]:
            if not isinstance(item, dict):
                new_trace.append(item)
                continue
            item = dict(item)
            if "query" in item:
                item["query"] = mask_text(str(item["query"]))
            if "results" in item:
                new_results = []
                for r in item["results"]:
                    if isinstance(r, dict):
                        r = dict(r)
                        for field in ("title", "snippet"):
                            if field in r:
                                r[field] = mask_text(str(r[field]))
                    new_results.append(r)
                item["results"] = new_results
            new_trace.append(item)
        masked["search_trace"] = new_trace

    # compress: compressed_research text
    if "compressed_research" in masked:
        new_cr = []
        for item in masked["compressed_research"]:
            if not isinstance(item, dict):
                new_cr.append(item)
                continue
            item = dict(item)
            for field in ("compressed_research", "summary"):
                if field in item:
                    item[field] = mask_text(str(item[field]))
            new_cr.append(item)
        masked["compressed_research"] = new_cr

    # write: final_report
    if "final_report" in masked:
        masked["final_report"] = mask_text(str(masked["final_report"]))

    masked["_masked"] = True
    return masked


def main() -> None:
    parser = argparse.ArgumentParser(description="Identifier masking for DRA artifacts")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--run-id", type=str)
    src.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.run_id:
        artifact_dir = args.artifact_dir or (ROOT / "runs" / "confirmatory")
        paths = [artifact_dir / f"{args.run_id}_artifacts.json"]
    else:
        paths = sorted(args.artifact_dir.glob("*_artifacts.json"))
        if args.seed is not None:
            suffix = f"_seed{args.seed}_artifacts.json"
            paths = [p for p in paths if p.name.endswith(suffix)]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Masking {len(paths)} artifacts → {args.output_dir}\n")

    for i, path in enumerate(paths, 1):
        run_id = path.name.replace("_artifacts.json", "")
        try:
            artifacts = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[{i}/{len(paths)}] SKIP {run_id}: {exc}")
            continue

        out_path = args.output_dir / f"{run_id}_masked_artifacts.json"
        if out_path.exists():
            print(f"[{i}/{len(paths)}] SKIP {run_id} (already masked)")
            continue

        print(f"[{i}/{len(paths)}] {run_id} ...", end=" ", flush=True)
        masked = mask_artifact(artifacts)
        out_path.write_text(json.dumps(masked, indent=2, ensure_ascii=False))
        print("OK")

    print(f"\nDone. Masked artifacts in {args.output_dir}")
    print("Next: run llm_matcher.py with --artifact-dir pointing to this directory")
    print("      and rename *_masked_artifacts.json → *_artifacts.json if needed,")
    print("      or pass --run-id directly.")


if __name__ == "__main__":
    main()
