"""Paired full-pipeline vs write-only no-brief Writing Acc@1 analysis.

Network-free. Requires:
  - runs/confirmatory/matches_hardneg_v1/pilot_*_match.json
  - runs/ablation/nobrief_writeonly/matches/ablation_nobrief_*_match.json
  - optional: nobrief summary files for report length diagnostics

Usage:
  python scripts/analyze_nobrief_paired.py
  python scripts/analyze_nobrief_paired.py --nobrief-dir runs/ablation/nobrief_writeonly
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FULL_MATCH = ROOT / "runs" / "confirmatory" / "matches_hardneg_v1"
DEFAULT_NOBRIEF = ROOT / "runs" / "ablation" / "nobrief_writeonly"

RUN_RE = re.compile(r"task(?P<taskid>\d+)_User(?P<user>\d+)_seed(?P<seed>\d+)")


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def _load_write_match(path: Path) -> dict[str, Any]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"Expected list in {path}")
    writes = [r for r in records if r.get("stage") == "write"]
    if len(writes) != 1:
        raise ValueError(f"Expected one write stage in {path}, got {len(writes)}")
    return writes[0]


def _load_stage_flags(path: Path) -> dict[str, bool]:
    records = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, bool] = {}
    for r in records:
        stage = r.get("stage")
        if stage in ("plan", "search", "compress", "write"):
            out[stage] = bool(r.get("correct"))
            if stage == "write":
                out["write_pred"] = r.get("predicted_userid")  # type: ignore[assignment]
                out["gt"] = r.get("gt_userid")  # type: ignore[assignment]
    return out


def _taskid(run_id: str) -> int:
    m = RUN_RE.search(run_id)
    if not m:
        raise ValueError(f"Cannot parse {run_id}")
    return int(m.group("taskid"))


def analyze(nobrief_dir: Path, full_match_dir: Path, bootstrap_reps: int = 2000) -> dict[str, Any]:
    match_dir = nobrief_dir / "matches"
    pairs: list[dict[str, Any]] = []
    short_reports: list[dict[str, Any]] = []

    for match_path in sorted(match_dir.glob("ablation_nobrief_*_match.json")):
        nobrief = _load_write_match(match_path)
        nobrief_run = str(nobrief["run_id"])
        source_run = nobrief_run.replace("ablation_nobrief_", "pilot_", 1)
        full_path = full_match_dir / f"{source_run}_match.json"
        if not full_path.exists():
            raise FileNotFoundError(full_path)
        full_flags = _load_stage_flags(full_path)

        summary_path = nobrief_dir / f"{nobrief_run}_summary.json"
        new_chars = None
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            new_chars = summary.get("new_report_chars")
            if isinstance(new_chars, int) and new_chars < 2000:
                short_reports.append(
                    {
                        "nobrief_run_id": nobrief_run,
                        "new_report_chars": new_chars,
                    }
                )

        pair = {
            "source_run_id": source_run,
            "nobrief_run_id": nobrief_run,
            "gt": full_flags.get("gt") or nobrief.get("gt_userid"),
            "taskid": _taskid(source_run),
            "full_write_correct": bool(full_flags.get("write")),
            "nobrief_write_correct": bool(nobrief.get("correct")),
            "full_plan_correct": bool(full_flags.get("plan")),
            "full_search_correct": bool(full_flags.get("search")),
            "full_pred": full_flags.get("write_pred"),
            "nobrief_pred": nobrief.get("predicted_userid"),
            "nobrief_reasoning": (nobrief.get("reasoning") or "")[:200],
            "new_report_chars": new_chars,
        }
        pairs.append(pair)

    n = len(pairs)
    if n == 0:
        raise RuntimeError(f"No nobrief matches found in {match_dir}")

    full_acc = sum(1 for p in pairs if p["full_write_correct"]) / n
    nobrief_acc = sum(1 for p in pairs if p["nobrief_write_correct"]) / n
    delta = nobrief_acc - full_acc

    both_c = sum(1 for p in pairs if p["full_write_correct"] and p["nobrief_write_correct"])
    both_w = sum(1 for p in pairs if (not p["full_write_correct"]) and (not p["nobrief_write_correct"]))
    full_only = sum(1 for p in pairs if p["full_write_correct"] and (not p["nobrief_write_correct"]))
    nobrief_only = sum(1 for p in pairs if (not p["full_write_correct"]) and p["nobrief_write_correct"])

    recovery = [
        p
        for p in pairs
        if p["full_plan_correct"] and (not p["full_search_correct"])
    ]
    recovery_stats = {
        "n": len(recovery),
        "full_write_correct": sum(1 for p in recovery if p["full_write_correct"]),
        "nobrief_write_correct": sum(1 for p in recovery if p["nobrief_write_correct"]),
    }

    # Task-cluster bootstrap of delta
    by_task: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for p in pairs:
        by_task[int(p["taskid"])].append(p)
    taskids = sorted(by_task)
    rng = random.Random(42)
    boot_vals: list[float] = []
    for _ in range(bootstrap_reps):
        sampled: list[dict[str, Any]] = []
        for tid in rng.choices(taskids, k=len(taskids)):
            sampled.extend(by_task[tid])
        if not sampled:
            continue
        f = sum(1 for p in sampled if p["full_write_correct"]) / len(sampled)
        nb = sum(1 for p in sampled if p["nobrief_write_correct"]) / len(sampled)
        boot_vals.append(nb - f)
    ci = (
        round(_percentile(boot_vals, 0.025), 3),
        round(_percentile(boot_vals, 0.975), 3),
    )

    lost = [
        p["source_run_id"]
        for p in pairs
        if p["full_write_correct"] and not p["nobrief_write_correct"]
    ]
    gained = [
        p["source_run_id"]
        for p in pairs
        if (not p["full_write_correct"]) and p["nobrief_write_correct"]
    ]

    return {
        "n": n,
        "full_write_acc": round(full_acc, 3),
        "nobrief_write_acc": round(nobrief_acc, 3),
        "delta_nobrief_minus_full": round(delta, 3),
        "task_bootstrap_95ci_delta": list(ci),
        "paired_counts": {
            "both_correct": both_c,
            "both_wrong": both_w,
            "full_only_correct": full_only,
            "nobrief_only_correct": nobrief_only,
        },
        "lost_after_brief_removal": lost,
        "gained_after_brief_removal": gained,
        "plan_correct_search_wrong_subset": recovery_stats,
        "pairs": pairs,
        "short_reports": short_reports,
        "n_task_clusters": len(taskids),
        "bootstrap_reps": bootstrap_reps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nobrief-dir", type=Path, default=DEFAULT_NOBRIEF)
    parser.add_argument("--full-match-dir", type=Path, default=DEFAULT_FULL_MATCH)
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: <nobrief-dir>/analysis_paired.json",
    )
    args = parser.parse_args(argv)
    out = args.output or (args.nobrief_dir / "analysis_paired.json")
    result = analyze(args.nobrief_dir, args.full_match_dir, args.bootstrap_reps)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(out),
                "n": result["n"],
                "full_write_acc": result["full_write_acc"],
                "nobrief_write_acc": result["nobrief_write_acc"],
                "delta": result["delta_nobrief_minus_full"],
                "ci": result["task_bootstrap_95ci_delta"],
                "paired_counts": result["paired_counts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
