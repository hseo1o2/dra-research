"""Compare Solar and secondary-matcher attribution decisions.

Network-free. The default comparison is the frozen PDR seed-0 reference
configuration: 60 reports x 4 stages = 240 paired decisions.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_matches import STAGES, load_match_records

DEFAULT_SOLAR = ROOT / "runs" / "confirmatory" / "matches_hardneg_v1"
DEFAULT_SECONDARY = (
    ROOT / "runs" / "confirmatory" / "gpt54nano_seed0_matches"
)
DEFAULT_OUTPUT = (
    ROOT / "runs" / "confirmatory" / "analysis_matcher_agreement"
)


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["run_id"]), str(row["stage"])


def cohen_kappa(
    left_labels: list[str],
    right_labels: list[str],
) -> dict[str, float | int]:
    if len(left_labels) != len(right_labels) or not left_labels:
        raise ValueError("Cohen's kappa requires equal non-empty label lists")
    n = len(left_labels)
    observed = sum(a == b for a, b in zip(left_labels, right_labels)) / n
    left_counts = Counter(left_labels)
    right_counts = Counter(right_labels)
    labels = set(left_counts) | set(right_counts)
    expected = sum(
        (left_counts[label] / n) * (right_counts[label] / n)
        for label in labels
    )
    kappa = (
        (observed - expected) / (1 - expected)
        if expected < 1
        else 1.0
    )
    return {
        "n": n,
        "observed_agreement": observed,
        "expected_agreement": expected,
        "cohen_kappa": kappa,
    }


def analyze(
    solar: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    seed: int = 0,
    expected_pairs: int = 240,
) -> dict[str, Any]:
    solar_map = {
        _key(row): row for row in solar if int(row["seed"]) == seed
    }
    secondary_map = {
        _key(row): row for row in secondary if int(row["seed"]) == seed
    }
    if len(solar_map) != expected_pairs:
        raise ValueError(
            f"Solar seed {seed}: expected {expected_pairs}, got {len(solar_map)}"
        )
    if len(secondary_map) != expected_pairs:
        raise ValueError(
            f"Secondary seed {seed}: expected {expected_pairs}, "
            f"got {len(secondary_map)}"
        )
    if set(solar_map) != set(secondary_map):
        raise ValueError(
            "Matcher pair keys differ: "
            f"{len(set(solar_map) - set(secondary_map))} Solar-only, "
            f"{len(set(secondary_map) - set(solar_map))} secondary-only"
        )

    order_mismatches = [
        key for key in solar_map
        if solar_map[key]["shuffled_order"]
        != secondary_map[key]["shuffled_order"]
    ]
    candidate_mismatches = [
        key for key in solar_map
        if set(solar_map[key]["candidate_userids"])
        != set(secondary_map[key]["candidate_userids"])
    ]
    if order_mismatches or candidate_mismatches:
        raise ValueError(
            f"Candidate comparability failed: order={len(order_mismatches)}, "
            f"set={len(candidate_mismatches)}"
        )

    rows: list[dict[str, Any]] = []
    for stage in (*STAGES, "all"):
        keys = sorted(
            key for key in solar_map
            if stage == "all" or key[1] == stage
        )
        solar_labels = [
            str(solar_map[key]["predicted_userid"]) for key in keys
        ]
        secondary_labels = [
            str(secondary_map[key]["predicted_userid"]) for key in keys
        ]
        agreement = cohen_kappa(solar_labels, secondary_labels)
        rows.append({
            "stage": stage,
            **agreement,
            "solar_accuracy": sum(
                bool(solar_map[key]["correct"]) for key in keys
            ) / len(keys),
            "secondary_accuracy": sum(
                bool(secondary_map[key]["correct"]) for key in keys
            ) / len(keys),
            "both_correct": sum(
                bool(solar_map[key]["correct"])
                and bool(secondary_map[key]["correct"])
                for key in keys
            ),
            "solar_only_correct": sum(
                bool(solar_map[key]["correct"])
                and not bool(secondary_map[key]["correct"])
                for key in keys
            ),
            "secondary_only_correct": sum(
                not bool(solar_map[key]["correct"])
                and bool(secondary_map[key]["correct"])
                for key in keys
            ),
            "both_wrong": sum(
                not bool(solar_map[key]["correct"])
                and not bool(secondary_map[key]["correct"])
                for key in keys
            ),
        })
    return {
        "schema_version": 1,
        "external_api_calls": 0,
        "seed": seed,
        "paired_decisions": expected_pairs,
        "candidate_set_mismatches": 0,
        "candidate_order_mismatches": 0,
        "agreement": rows,
        "claim_boundary": (
            "Matcher agreement measures replication across evaluators; it "
            "does not establish human validity or user utility."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solar-dir", type=Path, default=DEFAULT_SOLAR)
    parser.add_argument(
        "--secondary-dir", type=Path, default=DEFAULT_SECONDARY
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--expected-pairs", type=int, default=240)
    args = parser.parse_args()

    result = analyze(
        load_match_records(args.solar_dir),
        load_match_records(args.secondary_dir),
        args.seed,
        args.expected_pairs,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "matcher_agreement_summary.json"
    path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Matcher agreement → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
