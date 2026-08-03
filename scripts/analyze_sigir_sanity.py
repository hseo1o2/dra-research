"""Freeze and describe the five public SIGIR 2026 PDR report examples.

This is an offline, descriptive sanity check. It does not call any model,
search, or web API and it does not estimate DRA-PULSE attribution accuracy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UPSTREAM = ROOT / "data" / "sigir2026-pdr-upstream"
DEFAULT_MANIFEST = ROOT / "provenance" / "sigir_pdr_sanity_manifest.json"
DEFAULT_SUMMARY = ROOT / "provenance" / "sigir_pdr_sanity_summary.json"
UPSTREAM_URL = "https://github.com/Applied-Machine-Learning-Lab/SIGIR2026_PDR"

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?")
URL_RE = re.compile(r"https?://[^\s]+")
WORD_RANGE_RE = re.compile(
    r"(\d[\d,]*)\s*[–—-]\s*(\d[\d,]*)\s*[- ]?word",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_metrics(text: str) -> dict[str, int]:
    lines = text.splitlines()
    return {
        "bytes_utf8": len(text.encode("utf-8")),
        "characters": len(text),
        "words": len(TOKEN_RE.findall(text)),
        "paragraphs": len(
            [part for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
        ),
        "markdown_headings": sum(
            1 for line in lines if re.match(r"^\s{0,3}#{1,6}\s", line)
        ),
        "bullet_lines": sum(
            1 for line in lines if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", line)
        ),
        "urls": len(URL_RE.findall(text)),
    }


def requested_word_range(prompt: str) -> tuple[int, int] | None:
    match = WORD_RANGE_RE.search(prompt)
    if match is None:
        return None
    return tuple(int(value.replace(",", "")) for value in match.groups())


def token_jaccard(left: str, right: str) -> float:
    left_tokens = {token.lower() for token in TOKEN_RE.findall(left)}
    right_tokens = {token.lower() for token in TOKEN_RE.findall(right)}
    union = left_tokens | right_tokens
    return round(len(left_tokens & right_tokens) / len(union), 4) if union else 0.0


def _upstream_commit(upstream: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=upstream,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Cannot resolve upstream commit at {upstream}") from exc


def analyze(upstream: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    report_root = upstream / "data" / "report"
    authors = sorted(path for path in report_root.iterdir() if path.is_dir())
    if len(authors) != 5:
        raise ValueError(f"Expected exactly 5 report folders, found {len(authors)}")

    samples: list[dict[str, Any]] = []
    for index, author_dir in enumerate(authors, 1):
        paths = {
            "input": author_dir / "input.txt",
            "note": author_dir / "note",
            "output": author_dir / "output.txt",
        }
        missing = [name for name, path in paths.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"{author_dir}: missing {', '.join(missing)}")

        texts = {
            name: path.read_text(encoding="utf-8") for name, path in paths.items()
        }
        word_range = requested_word_range(texts["input"])
        output_words = text_metrics(texts["output"])["words"]
        samples.append(
            {
                "sanity_id": f"sigir_report_{index:02d}",
                "public_author_folder": author_dir.name,
                "source_urls": URL_RE.findall(texts["note"]),
                "files": {
                    name: {
                        "path": str(path.relative_to(upstream)),
                        "sha256": sha256_file(path),
                    }
                    for name, path in paths.items()
                },
                "metrics": {
                    name: text_metrics(text) for name, text in texts.items()
                },
                "requested_output_words": (
                    {"minimum": word_range[0], "maximum": word_range[1]}
                    if word_range
                    else None
                ),
                "output_within_requested_word_range": (
                    word_range[0] <= output_words <= word_range[1]
                    if word_range
                    else None
                ),
                "prompt_output_token_jaccard": token_jaccard(
                    texts["input"], texts["output"]
                ),
            }
        )

    manifest = {
        "schema_version": 1,
        "role": "descriptive human-authored sanity check only",
        "upstream": {
            "repository": UPSTREAM_URL,
            "commit": _upstream_commit(upstream),
            "license_file": "LICENSE.txt",
            "license_sha256": sha256_file(upstream / "LICENSE.txt"),
            "license_identifier": "Apache-2.0",
        },
        "sample_count": len(samples),
        "selection": (
            "Complete enumeration of the five report folders present in the "
            "official repository at the frozen commit; sorted by folder name."
        ),
        "samples": samples,
    }

    output_word_counts = [
        sample["metrics"]["output"]["words"] for sample in samples
    ]
    summary = {
        "schema_version": 1,
        "manifest_role": manifest["role"],
        "sample_count": len(samples),
        "output_words": {
            "minimum": min(output_word_counts),
            "maximum": max(output_word_counts),
            "mean": round(mean(output_word_counts), 1),
        },
        "within_requested_word_range": sum(
            sample["output_within_requested_word_range"] is True
            for sample in samples
        ),
        "all_files_hash_frozen": all(
            len(file_info["sha256"]) == 64
            for sample in samples
            for file_info in sample["files"].values()
        ),
        "interpretation_limits": [
            "The five folders are a complete public convenience sample, not a random sample.",
            "The repository note files contain source URLs, not full persona profiles.",
            "These human-authored outputs can sanity-check format and length only.",
            "No stage-wise attribution, causal, or generalization claim follows from this analysis.",
        ],
    }
    return manifest, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args(argv)

    manifest, summary = analyze(args.upstream.resolve())
    for path, payload in (
        (args.manifest_out, manifest),
        (args.summary_out, summary),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        f"Frozen {manifest['sample_count']} SIGIR report samples at "
        f"{manifest['upstream']['commit']}"
    )
    print(f"Manifest: {args.manifest_out}")
    print(f"Summary: {args.summary_out}")
    print("External API calls: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
