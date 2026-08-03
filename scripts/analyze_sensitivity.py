"""Analyze N=2/N=3/N=5 candidate-set sensitivity results.

Computes stage-wise accuracy for each N and reports the trajectory shape
(dip-and-recovery) relative to chance (1/N) across all three candidate sizes.

Usage:
    python scripts/analyze_sensitivity.py
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES = ("plan", "search", "compress", "write")

MATCH_DIRS = {
    2: ROOT / "runs/confirmatory/matches_sensitivity_n2",
    3: ROOT / "runs/confirmatory/matches_hardneg_v1",
    5: ROOT / "runs/confirmatory/matches_sensitivity_n5",
}


def load_matches(match_dir: Path, seed_filter: int | None = 0) -> list[dict]:
    records = []
    for path in sorted(match_dir.glob("*_match.json")):
        if seed_filter is not None and f"_seed{seed_filter}_" not in path.name:
            continue
        data = json.loads(path.read_text())
        if isinstance(data, list):
            records.extend(data)
    return records


def stage_accuracy(records: list[dict]) -> dict[str, float]:
    stage_correct: dict[str, list[int]] = defaultdict(list)
    for rec in records:
        stage = rec.get("stage", "")
        if stage in STAGES:
            stage_correct[stage].append(int(bool(rec.get("correct", False))))
    return {s: round(statistics.mean(v), 3) if v else float("nan") for s, v in stage_correct.items()}


def main() -> None:
    print("Candidate-set sensitivity analysis (seed 0)")
    print(f"{'N':>4}  {'Chance':>6}  {'Plan':>6}  {'Search':>6}  {'Compress':>8}  {'Write':>6}  {'Avg':>6}  {'Reports':>7}")
    print("-" * 65)

    results = {}
    for n, match_dir in sorted(MATCH_DIRS.items()):
        if not match_dir.exists():
            print(f"  N={n}: directory not found, skipping")
            continue
        records = load_matches(match_dir, seed_filter=0)
        if not records:
            print(f"  N={n}: no records found")
            continue
        acc = stage_accuracy(records)
        chance = round(1 / n, 3)
        avg = round(statistics.mean(acc[s] for s in STAGES if acc.get(s) == acc.get(s)), 3)
        n_reports = len(set(rec["run_id"] for rec in records))
        results[n] = {"acc": acc, "chance": chance, "avg": avg, "n_reports": n_reports}

        row = f"  {n:>2}  {chance:6.3f}  {acc.get('plan', float('nan')):6.3f}  {acc.get('search', float('nan')):6.3f}  {acc.get('compress', float('nan')):8.3f}  {acc.get('write', float('nan')):6.3f}  {avg:6.3f}  {n_reports:7d}"
        print(row)

    print()
    if len(results) >= 2:
        print("Trajectory shape check (dip-and-recovery across N):")
        for n, r in sorted(results.items()):
            acc = r["acc"]
            plan = acc.get("plan", float("nan"))
            search = acc.get("search", float("nan"))
            write = acc.get("write", float("nan"))
            dip = round(search - plan, 3) if plan == plan and search == search else float("nan")
            recovery = round(write - search, 3) if search == search and write == write else float("nan")
            above_chance = "✓" if plan > r["chance"] and write > r["chance"] else "✗"
            print(f"  N={n}: Plan→Search Δ={dip:+.3f}  Search→Write Δ={recovery:+.3f}  above-chance {above_chance}")

    # Write JSON summary
    summary_path = ROOT / "paper/analysis/sensitivity_summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()
