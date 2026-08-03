"""Post-processing shortcut control: NER and persona-derived identity masking.

Replaces PERSON / ORG / GPE / NORP / FAC entity spans in every text field
of a DRA artifact with the placeholder [MASKED]. With ``--identity-derived``,
it additionally masks exact identity-field phrases for all candidate
personas, including occupation, age, education, residence, and family fields.
The masked artifact is written to <output_dir>/<run_id>_masked_artifacts.json
and can be fed directly to llm_matcher.py or baseline_matcher.py.

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
import hashlib
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
IDENTITY_MASK_VERSION = "candidate_identity_phrases_v1"

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


def _identity_values(
    obj: Any,
    identity_leaf_keys: set[str],
) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in identity_leaf_keys and isinstance(value, str):
                values.append((key, value))
            else:
                values.extend(_identity_values(value, identity_leaf_keys))
    elif isinstance(obj, list):
        for value in obj:
            values.extend(_identity_values(value, identity_leaf_keys))
    return values


def _phrase_variants(field: str, value: str) -> set[str]:
    """Return conservative exact phrases derived from an identity leaf."""
    normalized = re.sub(r"\s+", " ", value).strip(" \t\r\n.,;:")
    if not normalized:
        return set()
    phrases = {normalized}

    if field in {
        "Name", "Age", "Gender", "Occupation", "Permanent Residence",
        "Hometown",
    }:
        phrases.update(
            part.strip(" \t\r\n.,;:")
            for part in re.split(r"[,;/|]", normalized)
        )
    if field == "Name":
        phrases.update(normalized.split())
    if field == "Occupation":
        phrases.add(re.sub(r"^(?:an?|the)\s+", "", normalized, flags=re.I))

    # Long narrative fields are masked only as clauses, not as arbitrary
    # token n-grams, to avoid deleting generic report content.
    if field not in {"Name", "Age", "Gender"}:
        phrases.update(
            clause.strip(" \t\r\n.,;:")
            for clause in re.split(r"[.;]", normalized)
        )

    return {
        phrase for phrase in phrases
        if (
            len(phrase) >= 3
            and (
                len(phrase.split()) >= 2
                or field in {
                    "Name", "Age", "Gender", "Permanent Residence",
                    "Hometown",
                }
            )
        )
    }


def identity_phrases_for_candidates(
    candidate_userids: list[str],
    personas_by_id: dict[str, dict[str, Any]],
    identity_leaf_keys: set[str],
) -> list[str]:
    phrases: set[str] = set()
    for userid in candidate_userids:
        persona = personas_by_id[userid]
        for field, value in _identity_values(persona, identity_leaf_keys):
            phrases.update(_phrase_variants(field, value))
    return sorted(phrases, key=lambda phrase: (-len(phrase), phrase.lower()))


def mask_identity_phrases(
    text: str,
    phrases: list[str],
) -> tuple[str, int]:
    """Mask longest candidate identity phrases case-insensitively."""
    result = text
    replacements = 0
    for phrase in phrases:
        escaped = re.escape(phrase).replace(r"\ ", r"\s+")
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])",
            flags=re.IGNORECASE,
        )
        result, count = pattern.subn(MASK_TOKEN, result)
        replacements += count
    return result, replacements


def mask_artifact(
    artifacts: dict[str, Any],
    identity_phrases: list[str] | None = None,
    candidate_userids: list[str] | None = None,
) -> dict[str, Any]:
    """Return a deep copy of artifacts with identifiers masked."""
    masked = dict(artifacts)
    phrases = identity_phrases or []
    audit = {
        stage: {
            "identity_phrase_replacements": 0,
            "ner_replacements": 0,
        }
        for stage in ("plan", "search", "compress", "write")
    }

    def apply_mask(stage: str, value: Any) -> str:
        text = str(value)
        phrase_masked, phrase_count = mask_identity_phrases(text, phrases)
        ner_masked = mask_text(phrase_masked)
        ner_count = (
            ner_masked.count(MASK_TOKEN)
            - phrase_masked.count(MASK_TOKEN)
        )
        audit[stage]["identity_phrase_replacements"] += phrase_count
        audit[stage]["ner_replacements"] += max(0, ner_count)
        return ner_masked

    # plan: research_brief
    if "research_brief" in masked:
        masked["research_brief"] = apply_mask(
            "plan", masked["research_brief"]
        )

    # search: query strings + result snippets/titles. Historical artifacts
    # used "results"; the v2 tracing schema uses "sources".
    if "search_trace" in masked:
        new_trace = []
        for item in masked["search_trace"]:
            if not isinstance(item, dict):
                new_trace.append(item)
                continue
            item = dict(item)
            if "query" in item:
                item["query"] = apply_mask("search", item["query"])
            for collection_key in ("results", "sources"):
                if collection_key not in item:
                    continue
                new_results = []
                for r in item[collection_key]:
                    if isinstance(r, dict):
                        r = dict(r)
                        for field in ("title", "snippet", "query"):
                            if field in r:
                                r[field] = apply_mask("search", r[field])
                    new_results.append(r)
                item[collection_key] = new_results
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
                    item[field] = apply_mask("compress", item[field])
            new_cr.append(item)
        masked["compressed_research"] = new_cr

    # write: final_report
    if "final_report" in masked:
        masked["final_report"] = apply_mask("write", masked["final_report"])

    masked["_masked"] = True
    masked["_masking"] = {
        "protocol": (
            IDENTITY_MASK_VERSION if phrases else "spacy_ner_only_v1"
        ),
        "mask_token": MASK_TOKEN,
        "ner_labels": sorted(MASK_LABELS),
        "candidate_userids": candidate_userids or [],
        "identity_phrase_count": len(phrases),
        "identity_phrase_sha256": hashlib.sha256(
            "\n".join(phrases).encode("utf-8")
        ).hexdigest(),
        "stage_replacements": audit,
    }
    return masked


def main() -> None:
    parser = argparse.ArgumentParser(description="Identifier masking for DRA artifacts")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--run-id", type=str)
    src.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--canonical-output-names",
        action="store_true",
        help="Write <run_id>_artifacts.json for direct batch matcher input",
    )
    parser.add_argument(
        "--identity-derived",
        action="store_true",
        help=(
            "Also mask identity-field phrases from every candidate persona "
            "in the frozen per-GT candidate set"
        ),
    )
    args = parser.parse_args()

    manifest: dict[str, Any] | None = None
    personas_by_id: dict[str, dict[str, Any]] = {}
    identity_leaf_keys: set[str] = set()
    if args.identity_derived:
        from scripts.llm_matcher import load_personas

        manifest = json.loads((ROOT / "manifest.json").read_text())
        personas_by_id = load_personas()
        identity_leaf_keys = set(
            manifest["actionable_identity_split"]["identity_leaf_keys"]
        )

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
    summary_rows: list[dict[str, Any]] = []

    for i, path in enumerate(paths, 1):
        run_id = path.name.replace("_artifacts.json", "")
        try:
            artifacts = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[{i}/{len(paths)}] SKIP {run_id}: {exc}")
            continue

        suffix = (
            "_artifacts.json"
            if args.canonical_output_names
            else "_masked_artifacts.json"
        )
        out_path = args.output_dir / f"{run_id}{suffix}"
        if out_path.exists():
            print(f"[{i}/{len(paths)}] SKIP {run_id} (already masked)")
            continue

        print(f"[{i}/{len(paths)}] {run_id} ...", end=" ", flush=True)
        candidate_userids: list[str] = []
        phrases: list[str] = []
        if args.identity_derived:
            from scripts.candidate_protocol import lookup_pdr_candidates

            assert manifest is not None
            _, candidate_userids = lookup_pdr_candidates(run_id, manifest)
            phrases = identity_phrases_for_candidates(
                candidate_userids,
                personas_by_id,
                identity_leaf_keys,
            )
        masked = mask_artifact(
            artifacts,
            identity_phrases=phrases,
            candidate_userids=candidate_userids,
        )
        out_path.write_text(json.dumps(masked, indent=2, ensure_ascii=False))
        summary_rows.append({
            "run_id": run_id,
            "output_file": out_path.name,
            **masked["_masking"],
        })
        print("OK")

    if summary_rows:
        totals = {
            stage: {
                key: sum(
                    row["stage_replacements"][stage][key]
                    for row in summary_rows
                )
                for key in (
                    "identity_phrase_replacements",
                    "ner_replacements",
                )
            }
            for stage in ("plan", "search", "compress", "write")
        }
        summary = {
            "schema_version": 1,
            "external_api_calls": 0,
            "protocol": (
                IDENTITY_MASK_VERSION
                if args.identity_derived
                else "spacy_ner_only_v1"
            ),
            "artifacts": len(summary_rows),
            "stage_replacement_totals": totals,
            "runs": summary_rows,
        }
        (args.output_dir / "masking_audit_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(f"\nDone. Masked artifacts in {args.output_dir}")
    print("Next: run llm_matcher.py with --artifact-dir pointing to this directory")
    print("      and rename *_masked_artifacts.json → *_artifacts.json if needed,")
    print("      or pass --run-id directly.")


if __name__ == "__main__":
    main()
