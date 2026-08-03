"""Compare persona-conditioned search stability across generation seeds.

Network-free. For each task, this analysis contrasts:

1. within-persona, cross-seed overlap; and
2. between-persona, same-seed overlap.

The unit used for uncertainty is the frozen PDR task cluster.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "runs" / "confirmatory"
DEFAULT_OUTPUT = ROOT / "runs" / "confirmatory" / "analysis_source_stability"
RUN_RE = re.compile(
    r"_task(?P<taskid>\d+)_(?P<userid>User\d+)_seed(?P<seed>\d+)$"
)


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def normalize_query(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), path, parts.query, "")
    )


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def extract_search_sets(artifact: dict[str, Any]) -> dict[str, set[str]]:
    queries: set[str] = set()
    urls: set[str] = set()
    for call in artifact.get("search_trace", []):
        if not isinstance(call, dict) or call.get("attempted") is not True:
            continue
        query = normalize_query(str(call.get("query", "")))
        if query:
            queries.add(query)
        for source in call.get("sources", []):
            if not isinstance(source, dict):
                continue
            link = normalize_url(str(source.get("link", "")))
            if link:
                urls.add(link)
    return {"queries": queries, "urls": urls}


def load_artifacts(input_dir: Path) -> dict[tuple[int, str, int], dict[str, set[str]]]:
    artifacts: dict[tuple[int, str, int], dict[str, set[str]]] = {}
    for path in sorted(input_dir.glob("*_artifacts.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        run_id = str(value.get("run_id", ""))
        match = RUN_RE.search(run_id)
        if match is None:
            continue
        key = (
            int(match.group("taskid")),
            match.group("userid"),
            int(match.group("seed")),
        )
        if key in artifacts:
            raise ValueError(f"Duplicate artifact key: {key}")
        artifacts[key] = extract_search_sets(value)
    return artifacts


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    if not materialized:
        raise ValueError("Expected at least one overlap value")
    return mean(materialized)


def task_rows(
    artifacts: dict[tuple[int, str, int], dict[str, set[str]]],
    expected_seeds: tuple[int, int] = (0, 1),
) -> list[dict[str, Any]]:
    taskids = sorted({key[0] for key in artifacts})
    rows: list[dict[str, Any]] = []
    for taskid in taskids:
        users = sorted({key[1] for key in artifacts if key[0] == taskid})
        if len(users) != 3:
            raise ValueError(f"Task {taskid}: expected 3 users, got {len(users)}")
        expected = {
            (taskid, user, seed) for user in users for seed in expected_seeds
        }
        missing = sorted(expected - set(artifacts))
        if missing:
            raise ValueError(f"Task {taskid}: missing artifacts {missing}")

        row: dict[str, Any] = {"taskid": taskid, "personas": len(users)}
        for field in ("queries", "urls"):
            within = [
                jaccard(
                    artifacts[(taskid, user, expected_seeds[0])][field],
                    artifacts[(taskid, user, expected_seeds[1])][field],
                )
                for user in users
            ]
            between = [
                jaccard(
                    artifacts[(taskid, left, seed)][field],
                    artifacts[(taskid, right, seed)][field],
                )
                for seed in expected_seeds
                for left, right in combinations(users, 2)
            ]
            row[f"{field}_within_cross_seed"] = _mean(within)
            row[f"{field}_between_same_seed"] = _mean(between)
            row[f"{field}_within_minus_between"] = (
                row[f"{field}_within_cross_seed"]
                - row[f"{field}_between_same_seed"]
            )
            row[f"{field}_within_pairs"] = len(within)
            row[f"{field}_between_pairs"] = len(between)
        rows.append(row)
    return rows


def summarize(
    rows: list[dict[str, Any]],
    repetitions: int = 5000,
    seed: int = 20260803,
) -> dict[str, Any]:
    rng = random.Random(seed)
    metrics: dict[str, Any] = {}
    for field in ("queries", "urls"):
        differences = [
            float(row[f"{field}_within_minus_between"]) for row in rows
        ]
        bootstrap = [
            mean(rng.choices(differences, k=len(differences)))
            for _ in range(repetitions)
        ]
        metrics[field] = {
            "within_persona_cross_seed_mean": mean(
                float(row[f"{field}_within_cross_seed"]) for row in rows
            ),
            "between_persona_same_seed_mean": mean(
                float(row[f"{field}_between_same_seed"]) for row in rows
            ),
            "within_minus_between": mean(differences),
            "task_bootstrap_ci95": [
                _percentile(bootstrap, 0.025),
                _percentile(bootstrap, 0.975),
            ],
            "within_pair_count": sum(
                int(row[f"{field}_within_pairs"]) for row in rows
            ),
            "between_pair_count": sum(
                int(row[f"{field}_between_pairs"]) for row in rows
            ),
        }
    return {
        "schema_version": 1,
        "external_api_calls": 0,
        "estimand": (
            "Macro task-level Jaccard overlap: within-persona cross-seed "
            "minus between-persona same-seed."
        ),
        "normalization": {
            "query": "Unicode casefold and whitespace collapse",
            "url": "lowercase scheme/host, remove fragment/trailing slash; keep query",
        },
        "population": {
            "tasks": len(rows),
            "personas_per_task": 3,
            "seeds": [0, 1],
        },
        "metrics": metrics,
        "claim_boundary": (
            "Higher within-persona stability is consistent with persona-"
            "conditioned evidence acquisition, but is not a causal estimate."
        ),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260803)
    args = parser.parse_args()

    artifacts = load_artifacts(args.input_dir)
    rows = task_rows(artifacts)
    result = summarize(
        rows, args.bootstrap_repetitions, args.bootstrap_seed
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "source_stability_summary.json"
    summary_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(args.output_dir / "source_stability_by_task.csv", rows)
    print(f"Source stability analysis → {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
