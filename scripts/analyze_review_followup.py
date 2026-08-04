"""Tier-1 review follow-up analyses (network-free).

Produces:
1. Symmetric (task-shared) vs per-GT hard-neg trajectories with CIs
2. Chance-normalized Acc for N=2/3/5
3. Candidate-only-prior-adjusted stage accuracy
4. User10 exposure-normalized false attribution rates
5. Report-level transition CIs under both protocols

Usage:
  python scripts/analyze_review_followup.py
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STAGES = ("plan", "search", "compress", "write")
RUN_RE = re.compile(r"task(?P<taskid>\d+)_User(?P<user>\d+)_seed(?P<seed>\d+)")

from scripts.analyze_candidate_prior import (  # noqa: E402
    candidate_prior_audit,
    centrality_prediction,
)
from scripts.build_manifest import actionable_tokens, load_jsonl  # noqa: E402


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


def _load_matches(match_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(match_dir.glob("*_match.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rec in payload:
            run_id = str(rec["run_id"])
            m = RUN_RE.search(run_id)
            if not m:
                raise ValueError(run_id)
            rows.append(
                {
                    "run_id": run_id,
                    "stage": rec["stage"],
                    "gt_userid": rec["gt_userid"],
                    "predicted_userid": rec.get("predicted_userid"),
                    "correct": bool(rec["correct"]),
                    "candidate_userids": list(rec.get("candidate_userids") or []),
                    "taskid": int(m.group("taskid")),
                    "seed": int(m.group("seed")),
                    "user_num": int(m.group("user")),
                }
            )
    return rows


def _bootstrap_stat(
    rows: list[dict[str, Any]],
    stat_fn,
    reps: int,
    seed: int,
) -> tuple[float, float, float]:
    by_task: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_task[int(r["taskid"])].append(r)
    taskids = sorted(by_task)
    if not taskids:
        return float("nan"), float("nan"), float("nan")
    point = stat_fn(rows)
    rng = random.Random(seed)
    boots: list[float] = []
    for _ in range(reps):
        sampled: list[dict[str, Any]] = []
        for tid in rng.choices(taskids, k=len(taskids)):
            sampled.extend(by_task[tid])
        boots.append(stat_fn(sampled))
    return (
        round(point, 4),
        round(_percentile(boots, 0.025), 4),
        round(_percentile(boots, 0.975), 4),
    )


def trajectory_with_ci(
    rows: list[dict[str, Any]], reps: int = 2000, seed: int = 42
) -> dict[str, Any]:
    out: dict[str, Any] = {"stages": {}, "deltas": {}, "transitions": {}}
    for i, stage in enumerate(STAGES):
        stage_rows = [r for r in rows if r["stage"] == stage]

        def acc(rs, s=stage):
            vals = [r["correct"] for r in rs if r["stage"] == s]
            return sum(vals) / len(vals) if vals else float("nan")

        # rebind stage for bootstrap over full rows filtered inside
        def make_acc(s):
            def fn(rs):
                vals = [r["correct"] for r in rs if r["stage"] == s]
                return sum(vals) / len(vals) if vals else float("nan")

            return fn

        p, lo, hi = _bootstrap_stat(rows, make_acc(stage), reps, seed + i)
        out["stages"][stage] = {
            "acc": p,
            "ci95": [lo, hi],
            "n": sum(1 for r in stage_rows),
            "correct": sum(1 for r in stage_rows if r["correct"]),
        }

    def delta_fn(a: str, b: str):
        def fn(rs):
            by_run: dict[str, dict[str, bool]] = defaultdict(dict)
            for r in rs:
                if r["stage"] in (a, b):
                    by_run[r["run_id"]][r["stage"]] = r["correct"]
            pairs = [
                v for v in by_run.values() if a in v and b in v
            ]
            if not pairs:
                return float("nan")
            return sum(p[b] for p in pairs) / len(pairs) - sum(
                p[a] for p in pairs
            ) / len(pairs)

        return fn

    for name, a, b, s0 in [
        ("plan_to_search", "plan", "search", 100),
        ("search_to_compress", "search", "compress", 200),
        ("compress_to_write", "compress", "write", 300),
        ("search_to_write", "search", "write", 400),
    ]:
        p, lo, hi = _bootstrap_stat(rows, delta_fn(a, b), reps, seed + s0)
        out["deltas"][name] = {"delta": p, "ci95": [lo, hi]}

    # report-level Plan✓ Search✗ recovery
    by_run: dict[str, dict[str, Any]] = defaultdict(dict)
    for r in rows:
        by_run[r["run_id"]][r["stage"]] = r["correct"]
        by_run[r["run_id"]]["taskid"] = r["taskid"]
    loss_rows = []
    for run_id, st in by_run.items():
        if st.get("plan") is True and st.get("search") is False:
            loss_rows.append(
                {
                    "run_id": run_id,
                    "taskid": st["taskid"],
                    "write_recover": bool(st.get("write")),
                    "compress_recover": bool(st.get("compress")),
                }
            )
    n_loss = len(loss_rows)
    if n_loss:
        rec_rate = sum(1 for r in loss_rows if r["write_recover"]) / n_loss

        def rec_fn(rs):
            # rs are loss_rows clustered by task — bootstrap on loss_rows
            if not rs:
                return float("nan")
            return sum(1 for r in rs if r["write_recover"]) / len(rs)

        # bootstrap loss_rows by task
        by_task: dict[int, list] = defaultdict(list)
        for r in loss_rows:
            by_task[r["taskid"]].append(r)
        taskids = sorted(by_task)
        rng = random.Random(seed + 500)
        boots = []
        for _ in range(reps):
            sampled = []
            for tid in rng.choices(taskids, k=len(taskids)):
                sampled.extend(by_task[tid])
            if sampled:
                boots.append(sum(1 for r in sampled if r["write_recover"]) / len(sampled))
        out["transitions"]["plan_ok_search_wrong"] = {
            "n": n_loss,
            "write_recover_n": sum(1 for r in loss_rows if r["write_recover"]),
            "write_recover_rate": round(rec_rate, 4),
            "write_recover_ci95": [
                round(_percentile(boots, 0.025), 4),
                round(_percentile(boots, 0.975), 4),
            ],
        }
    else:
        out["transitions"]["plan_ok_search_wrong"] = {"n": 0}
    return out


def chance_normalized(acc: float, n: int) -> float:
    chance = 1.0 / n
    return (acc - chance) / (1.0 - chance) if chance < 1 else float("nan")


def n_sensitivity_table(
    dirs: dict[int, Path], reps: int = 2000
) -> dict[str, Any]:
    result = {}
    for n, path in sorted(dirs.items()):
        rows = _load_matches(path)
        traj = trajectory_with_ci(rows, reps=reps, seed=1000 + n)
        norm = {}
        for stage, info in traj["stages"].items():
            norm[stage] = {
                "acc": info["acc"],
                "chance": round(1 / n, 4),
                "chance_normalized": round(
                    chance_normalized(info["acc"], n), 4
                ),
                "ci95": info["ci95"],
            }
        result[f"N={n}"] = {
            "n_reports": traj["stages"]["plan"]["n"],
            "stages": norm,
            "deltas": traj["deltas"],
            "dip_preserved": (
                traj["stages"]["search"]["acc"] < traj["stages"]["plan"]["acc"]
                and traj["stages"]["write"]["acc"]
                > traj["stages"]["search"]["acc"]
            ),
        }
    return result


def prior_adjusted(
    hardneg_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    personas: list[dict[str, Any]],
    reps: int = 2000,
) -> dict[str, Any]:
    tokens = {
        str(p["userid"]): actionable_tokens(p) for p in personas
    }
    # map (taskid, gt) -> prior correct
    prior_ok: dict[tuple[int, str], bool] = {}
    for task in manifest["pdr_bench"]["confirmatory"]:
        tid = int(task["taskid"])
        for exp in task["experiments"]:
            cands = list(exp["attribution_candidate_set_n3"])
            pred, _ = centrality_prediction(cands, tokens)
            prior_ok[(tid, str(exp["gt_userid"]))] = pred == exp["gt_userid"]

    # attach to write-stage uniqueness: each run
    run_meta: dict[str, dict[str, Any]] = {}
    for r in hardneg_rows:
        if r["stage"] != "write":
            continue
        key = (r["taskid"], r["gt_userid"])
        run_meta[r["run_id"]] = {
            "taskid": r["taskid"],
            "gt": r["gt_userid"],
            "prior_correct": prior_ok.get(key, False),
        }

    def subset_traj(predicate):
        keep = {rid for rid, m in run_meta.items() if predicate(m)}
        sub = [r for r in hardneg_rows if r["run_id"] in keep]
        traj = trajectory_with_ci(sub, reps=reps, seed=77)
        return {
            "n_reports": len(keep),
            "trajectory": traj,
        }

    all_prior = candidate_prior_audit(manifest, personas)
    return {
        "candidate_only_prior": all_prior,
        "all_reports": subset_traj(lambda m: True),
        "prior_wrong_only": subset_traj(lambda m: not m["prior_correct"]),
        "prior_correct_only": subset_traj(lambda m: m["prior_correct"]),
        "interpretation": (
            "prior_wrong_only removes cases where artifact-free centrality "
            "already picks the GT; dip-and-recovery should still appear if "
            "transitions are not solely prior-driven."
        ),
    }


def user10_exposure(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """P(pred=User10 | User10 in C, User10 != GT) by stage."""
    by_stage: dict[str, dict[str, Any]] = {}
    for stage in STAGES:
        exposed = 0
        false_to_u10 = 0
        correct_u10 = 0
        gt_u10 = 0
        pred_u10 = 0
        for r in rows:
            if r["stage"] != stage:
                continue
            cands = r["candidate_userids"]
            if r["gt_userid"] == "User10":
                gt_u10 += 1
                if r["correct"]:
                    correct_u10 += 1
            if r["predicted_userid"] == "User10":
                pred_u10 += 1
            if "User10" in cands and r["gt_userid"] != "User10":
                exposed += 1
                if r["predicted_userid"] == "User10":
                    false_to_u10 += 1
        rate = false_to_u10 / exposed if exposed else float("nan")
        by_stage[stage] = {
            "exposure_n": exposed,
            "false_to_user10_n": false_to_u10,
            "false_rate_given_exposure": round(rate, 4)
            if exposed
            else None,
            "chance_among_3": round(1 / 3, 4),
            "gt_user10_n": gt_u10,
            "gt_user10_acc": round(correct_u10 / gt_u10, 4) if gt_u10 else None,
            "pred_user10_n": pred_u10,
        }
    return {
        "definition": "P(hat=User10 | User10 in candidates, GT!=User10)",
        "by_stage": by_stage,
        "note": (
            "If false_rate ≈ chance (0.333), User10 is not an above-chance "
            "attractor after exposure normalization."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "runs/confirmatory/analysis_review_followup",
    )
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    args = parser.parse_args(argv)

    hardneg = _load_matches(ROOT / "runs/confirmatory/matches_hardneg_v1")
    shared = _load_matches(ROOT / "runs/confirmatory/matches_sha256")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    personas = load_jsonl(
        ROOT / "data/pdr-bench/persona_data/personas_en.jsonl"
    )

    summary = {
        "schema_version": 1,
        "external_api_calls": 0,
        "primary_contrasts": [
            "plan_to_search",
            "compress_to_write",
            "plan_ok_search_wrong_write_recovery",
        ],
        "secondary": [
            "identity_masking",
            "matcher_replication",
            "equal_budget",
            "symmetric_task_shared",
        ],
        "exploratory": [
            "domain",
            "user10_attractor",
            "utility_correlation",
            "search_views",
        ],
        "hardneg_per_gt": trajectory_with_ci(
            hardneg, reps=args.bootstrap_reps, seed=1
        ),
        "symmetric_task_shared": trajectory_with_ci(
            shared, reps=args.bootstrap_reps, seed=2
        ),
        "n_sensitivity_chance_normalized": n_sensitivity_table(
            {
                2: ROOT / "runs/confirmatory/matches_sensitivity_n2",
                3: ROOT / "runs/confirmatory/matches_hardneg_v1",
                5: ROOT / "runs/confirmatory/matches_sensitivity_n5",
            },
            reps=args.bootstrap_reps,
        ),
        "prior_adjusted": prior_adjusted(
            hardneg, manifest, personas, reps=args.bootstrap_reps
        ),
        "user10_exposure": user10_exposure(hardneg),
        "construct_definition": (
            "Throughout this analysis, persona recoverability / persona signal "
            "means only information in an artifact that supports closed-set "
            "recovery of the conditioning persona among hard-negative "
            "candidates. It does not imply causal mediation, personalization "
            "utility, or factual quality."
        ),
    }

    # dip preserved flags
    for key in ("hardneg_per_gt", "symmetric_task_shared"):
        t = summary[key]["stages"]
        summary[key]["dip_preserved"] = (
            t["search"]["acc"] < t["plan"]["acc"]
            and t["write"]["acc"] > t["search"]["acc"]
        )

    pa = summary["prior_adjusted"]["prior_wrong_only"]["trajectory"]["stages"]
    summary["prior_adjusted"]["prior_wrong_only"]["dip_preserved"] = (
        pa["search"]["acc"] < pa["plan"]["acc"]
        and pa["write"]["acc"] > pa["search"]["acc"]
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / "review_followup_summary.json"
    out_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # compact print
    def fmt_traj(name, block):
        s = block["stages"]
        print(
            f"{name}: "
            f"{s['plan']['acc']:.3f}/{s['search']['acc']:.3f}/"
            f"{s['compress']['acc']:.3f}/{s['write']['acc']:.3f} "
            f"dip={block.get('dip_preserved')}"
        )
        d = block["deltas"]
        print(
            f"  ΔP→S={d['plan_to_search']['delta']} {d['plan_to_search']['ci95']} "
            f"ΔC→W={d['compress_to_write']['delta']} {d['compress_to_write']['ci95']}"
        )

    fmt_traj("hardneg", summary["hardneg_per_gt"])
    fmt_traj("symmetric", summary["symmetric_task_shared"])
    pw = summary["prior_adjusted"]["prior_wrong_only"]
    print(
        "prior_wrong_only n=",
        pw["n_reports"],
        "traj",
        {k: v["acc"] for k, v in pw["trajectory"]["stages"].items()},
        "dip",
        pw.get("dip_preserved"),
    )
    print("user10 false rates:", {
        s: summary["user10_exposure"]["by_stage"][s][
            "false_rate_given_exposure"
        ]
        for s in STAGES
    })
    print("N-sens normalized plan:", {
        k: v["stages"]["plan"]["chance_normalized"]
        for k, v in summary["n_sensitivity_chance_normalized"].items()
    })
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
