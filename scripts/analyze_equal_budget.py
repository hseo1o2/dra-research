"""Compare default-budget vs equal-char-budget Solar stage Acc@1.

Network-free. Intended for seed-0 hygiene control:
  default: runs/confirmatory/matches_hardneg_v1 (filter seed0)
  equal:   runs/confirmatory/matches_equal_budget_3500_seed0

Usage:
  python scripts/analyze_equal_budget.py
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
STAGES = ("plan", "search", "compress", "write")
RUN_RE = re.compile(r"task(?P<taskid>\d+)_.*_seed(?P<seed>\d+)")


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def _load_dir(match_dir: Path, seed: int | None) -> dict[str, dict[str, bool]]:
    """run_id -> stage -> correct"""
    out: dict[str, dict[str, bool]] = {}
    for path in sorted(match_dir.glob("*_match.json")):
        run_id = path.name.replace("_match.json", "")
        if seed is not None and not run_id.endswith(f"_seed{seed}"):
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        out[run_id] = {
            r["stage"]: bool(r["correct"])
            for r in rows
            if r.get("stage") in STAGES
        }
    return out


def _taskid(run_id: str) -> int:
    m = RUN_RE.search(run_id)
    if not m:
        raise ValueError(run_id)
    return int(m.group("taskid"))


def analyze(
    default_dir: Path,
    equal_dir: Path,
    seed: int,
    bootstrap_reps: int = 2000,
) -> dict[str, Any]:
    default = _load_dir(default_dir, seed=seed)
    equal = _load_dir(equal_dir, seed=None)  # dir already seed-filtered
    common = sorted(set(default) & set(equal))
    if not common:
        raise RuntimeError("No overlapping run_ids between default and equal dirs")

    stage_rows: dict[str, Any] = {}
    for stage in STAGES:
        pairs = []
        for run_id in common:
            if stage not in default[run_id] or stage not in equal[run_id]:
                continue
            pairs.append(
                {
                    "run_id": run_id,
                    "taskid": _taskid(run_id),
                    "default": default[run_id][stage],
                    "equal": equal[run_id][stage],
                }
            )
        n = len(pairs)
        d_acc = sum(p["default"] for p in pairs) / n
        e_acc = sum(p["equal"] for p in pairs) / n
        delta = e_acc - d_acc

        by_task: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for p in pairs:
            by_task[p["taskid"]].append(p)
        taskids = sorted(by_task)
        rng = random.Random(42 + STAGES.index(stage))
        boot: list[float] = []
        for _ in range(bootstrap_reps):
            sampled: list[dict[str, Any]] = []
            for tid in rng.choices(taskids, k=len(taskids)):
                sampled.extend(by_task[tid])
            if not sampled:
                continue
            da = sum(p["default"] for p in sampled) / len(sampled)
            ea = sum(p["equal"] for p in sampled) / len(sampled)
            boot.append(ea - da)
        ci = (
            round(_percentile(boot, 0.025), 3),
            round(_percentile(boot, 0.975), 3),
        )
        stage_rows[stage] = {
            "n": n,
            "default_acc": round(d_acc, 3),
            "equal_acc": round(e_acc, 3),
            "delta_equal_minus_default": round(delta, 3),
            "task_bootstrap_95ci_delta": list(ci),
            "both_correct": sum(1 for p in pairs if p["default"] and p["equal"]),
            "both_wrong": sum(1 for p in pairs if (not p["default"]) and (not p["equal"])),
            "default_only": sum(1 for p in pairs if p["default"] and not p["equal"]),
            "equal_only": sum(1 for p in pairs if (not p["default"]) and p["equal"]),
        }

    # trajectory shape: plan>search and write>search
    def shape(rows: dict[str, dict[str, bool]], key: str) -> dict[str, float]:
        accs = {}
        for stage in STAGES:
            vals = [rows[r][stage] for r in common if stage in rows[r]]
            accs[stage] = sum(vals) / len(vals) if vals else float("nan")
        return accs

    default_shape = {
        s: stage_rows[s]["default_acc"] for s in STAGES
    }
    equal_shape = {
        s: stage_rows[s]["equal_acc"] for s in STAGES
    }

    return {
        "n_reports": len(common),
        "seed": seed,
        "default_dir": str(default_dir),
        "equal_dir": str(equal_dir),
        "stages": stage_rows,
        "default_trajectory": default_shape,
        "equal_trajectory": equal_shape,
        "dip_preserved": (
            equal_shape["search"] < equal_shape["plan"]
            and equal_shape["write"] > equal_shape["search"]
        ),
        "run_ids": common,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--default-dir",
        type=Path,
        default=ROOT / "runs/confirmatory/matches_hardneg_v1",
    )
    parser.add_argument(
        "--equal-dir",
        type=Path,
        default=ROOT / "runs/confirmatory/matches_equal_budget_3500_seed0",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runs/confirmatory/analysis_equal_budget_3500_seed0/summary.json",
    )
    args = parser.parse_args(argv)
    result = analyze(args.default_dir, args.equal_dir, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "n": result["n_reports"],
                "dip_preserved": result["dip_preserved"],
                "stages": {
                    s: {
                        "default": result["stages"][s]["default_acc"],
                        "equal": result["stages"][s]["equal_acc"],
                        "delta": result["stages"][s]["delta_equal_minus_default"],
                        "ci": result["stages"][s]["task_bootstrap_95ci_delta"],
                    }
                    for s in STAGES
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
