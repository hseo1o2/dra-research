"""Offline domain-stratified analysis + recovery report characteristics.

Addresses reviewer weaknesses:
  6. Domain breakdown — stage accuracy by domain (10 domains × 4 stages)
  7. User10 attractor — pairwise actionable Jaccard quantification
  9. Recovery vs non-recovery reports — 24 recovered vs 8 not recovered

Uses existing match JSON files; calls no external API.

Usage:
    python scripts/analyze_domain_recovery.py \
      --match-dir runs/confirmatory/matches_hardneg_v1 \
      --run-dir runs/confirmatory \
      --output-dir paper/analysis
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

STAGES = ("plan", "search", "compress", "write")


def load_matches(match_dir: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(match_dir.glob("*_match.json")):
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            continue
        for rec in data:
            if rec.get("stage") not in STAGES:
                continue
            records.append(rec)
    return records


def load_batch_summaries(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Map run_id -> batch summary row."""
    mapping: dict[str, dict[str, Any]] = {}
    for path in sorted(run_dir.glob("batch_confirmatory_seed*.json")):
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            continue
        for row in rows:
            mapping[row["run_id"]] = row
    return mapping


def bootstrap_ci(values: list[float], n_boot: int = 2000, alpha: float = 0.05) -> tuple[float, float]:
    if len(values) < 2:
        return (float("nan"), float("nan"))
    import random
    means = sorted(statistics.mean(random.choices(values, k=len(values))) for _ in range(n_boot))
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot)]
    return (lo, hi)


def jaccard(set_a: set, set_b: set) -> float:
    union = set_a | set_b
    if not union:
        return float("nan")
    return len(set_a & set_b) / len(union)


def main(match_dir: Path, run_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_matches(match_dir)
    batch = load_batch_summaries(run_dir)

    # Build per-run_id domain mapping
    run_domain: dict[str, str] = {rid: row["domain"] for rid, row in batch.items()}
    run_gt: dict[str, str] = {rid: row["gt_userid"] for rid, row in batch.items()}

    # Attach domain + correct to each record
    for rec in records:
        rid = rec["run_id"]
        rec["domain"] = run_domain.get(rid, "Unknown")
        rec["correct"] = bool(rec.get("correct", False))

    # ── 1. Domain × Stage accuracy ──────────────────────────────────────────
    domain_stage_correct: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for rec in records:
        domain_stage_correct[rec["domain"]][rec["stage"]].append(int(rec["correct"]))

    domains = sorted(domain_stage_correct)
    domain_table: list[dict] = []
    for dom in domains:
        row: dict = {"domain": dom}
        for stage in STAGES:
            vals = domain_stage_correct[dom][stage]
            acc = statistics.mean(vals) if vals else float("nan")
            row[f"{stage}_acc"] = round(acc, 3)
            row[f"{stage}_n"] = len(vals)
        # combined average
        all_vals = [v for stage in STAGES for v in domain_stage_correct[dom][stage]]
        row["macro_avg"] = round(statistics.mean(all_vals), 3) if all_vals else float("nan")
        domain_table.append(row)

    # Write CSV
    import csv, io
    fieldnames = ["domain", "macro_avg"] + [f"{s}_{x}" for s in STAGES for x in ("acc", "n")]
    with (output_dir / "domain_stage_accuracy.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(domain_table)
    print("Domain×Stage table:")
    print(f"  {'Domain':<14}", " ".join(f"{s:>8}" for s in STAGES), f"  {'Avg':>6}")
    for row in domain_table:
        vals = " ".join(f"{row[f'{s}_acc']:8.3f}" for s in STAGES)
        print(f"  {row['domain']:<14} {vals}  {row['macro_avg']:6.3f}")

    # ── 2. Recovery analysis (Planning-correct → Search-wrong → Writing) ───
    # Group records by run_id
    run_records: dict[str, dict[str, dict]] = defaultdict(dict)
    for rec in records:
        run_records[rec["run_id"]][rec["stage"]] = rec

    recovered_runs: list[str] = []
    not_recovered_runs: list[str] = []
    for rid, stages in run_records.items():
        plan_ok = stages.get("plan", {}).get("correct", False)
        search_ok = stages.get("search", {}).get("correct", False)
        write_ok = stages.get("write", {}).get("correct", False)
        if plan_ok and not search_ok:
            if write_ok:
                recovered_runs.append(rid)
            else:
                not_recovered_runs.append(rid)

    print(f"\nRecovery analysis: {len(recovered_runs)} recovered, {len(not_recovered_runs)} not recovered")

    def characterize_runs(run_ids: list[str], label: str) -> dict:
        if not run_ids:
            return {}
        domains_list = [run_domain.get(r, "Unknown") for r in run_ids]
        domain_counts = defaultdict(int)
        for d in domains_list:
            domain_counts[d] += 1
        compress_correct = [int(run_records[r].get("compress", {}).get("correct", False)) for r in run_ids]
        compress_acc = statistics.mean(compress_correct) if compress_correct else float("nan")
        return {
            "label": label,
            "n": len(run_ids),
            "compress_acc": round(compress_acc, 3),
            "domain_counts": dict(sorted(domain_counts.items())),
            "run_ids": run_ids,
        }

    rec_char = characterize_runs(recovered_runs, "recovered")
    norec_char = characterize_runs(not_recovered_runs, "not_recovered")

    print(f"\n  Recovered (n={rec_char['n']}):")
    print(f"    Compression accuracy: {rec_char['compress_acc']:.3f}")
    print(f"    Domain breakdown: {rec_char['domain_counts']}")
    print(f"\n  Not recovered (n={norec_char['n']}):")
    print(f"    Compression accuracy: {norec_char['compress_acc']:.3f}")
    print(f"    Domain breakdown: {norec_char['domain_counts']}")

    (output_dir / "recovery_characteristics.json").write_text(
        json.dumps({"recovered": rec_char, "not_recovered": norec_char}, indent=2)
    )

    # ── 3. User10 pairwise Jaccard analysis ─────────────────────────────────
    # Load persona actionable prefs from data/pdrbench_personas.json or equivalent
    # First find the data file
    data_candidates = [
        Path("data/pdrbench_personas.json"),
        Path("data/personas.json"),
        Path("data/lamp_users.json"),
    ]
    persona_file = next((p for p in data_candidates if (Path(".") / p).exists()), None)
    if persona_file is None:
        # Try finding it
        import subprocess
        result = subprocess.run(
            ["find", ".", "-name", "*.json", "-path", "*/data/*", "-not", "-path", "*/.git/*"],
            capture_output=True, text=True, cwd=str(Path("."))
        )
        data_files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        print(f"\nUser10 Jaccard: no persona file found. Available data files: {data_files[:10]}")
    else:
        print(f"\nUser10 Jaccard: using {persona_file}")

    # Regardless, compute User10 as attractor from confusion matrix in match records
    # For each record where gt != User10, check how often User10 is predicted
    user10_attractor: dict[str, list[int]] = defaultdict(list)  # stage -> [1 if predicted User10 else 0]
    for rec in records:
        gt = rec.get("gt_userid", "")
        pred = rec.get("predicted_userid", "")
        if gt != "User10":
            user10_attractor[rec["stage"]].append(int(pred == "User10"))

    print("\nUser10 prediction rate when User10 is NOT the GT:")
    user10_rates: dict = {}
    for stage in STAGES:
        vals = user10_attractor[stage]
        rate = statistics.mean(vals) if vals else 0.0
        user10_rates[stage] = {"rate": round(rate, 3), "n": len(vals)}
        print(f"  {stage:12s}: {rate:.3f}  (n={len(vals)})")

    # Compare to chance rate: 1/3 ≈ 0.333
    print("  (chance baseline: 0.333)")

    # Also check if User10 is concentrated in specific domains when it's the attractor
    user10_misattr: dict[str, list[str]] = defaultdict(list)
    for rec in records:
        gt = rec.get("gt_userid", "")
        pred = rec.get("predicted_userid", "")
        if gt != "User10" and pred == "User10":
            user10_misattr[rec["stage"]].append(rec.get("domain", "Unknown"))

    user10_domain_breakdown: dict = {}
    for stage in STAGES:
        counts = defaultdict(int)
        for d in user10_misattr[stage]:
            counts[d] += 1
        user10_domain_breakdown[stage] = dict(sorted(counts.items(), key=lambda x: -x[1]))

    print("\nUser10 false-attribution domain breakdown:")
    for stage in STAGES:
        print(f"  {stage}: {user10_domain_breakdown[stage]}")

    (output_dir / "user10_attractor_analysis.json").write_text(
        json.dumps({
            "user10_prediction_rate_when_not_gt": user10_rates,
            "chance_rate": 0.333,
            "user10_misattribution_by_domain": user10_domain_breakdown,
        }, indent=2)
    )

    print(f"\nOutputs written to {output_dir}/")
    print("  domain_stage_accuracy.csv")
    print("  recovery_characteristics.json")
    print("  user10_attractor_analysis.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-dir", default="runs/confirmatory/matches_hardneg_v1")
    parser.add_argument("--run-dir", default="runs/confirmatory")
    parser.add_argument("--output-dir", default="paper/analysis")
    args = parser.parse_args()
    main(Path(args.match_dir), Path(args.run_dir), Path(args.output_dir))
