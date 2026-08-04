"""LLM personalization utility judge for frozen DRA final reports.

Scores each confirmatory final report on content/presentation personalization
using a cheap OpenAI model (default: gpt-4o-mini). Correlates scores with
existing stage-attribution correctness.

Usage:
  # estimate only
  open_deep_research/.venv/bin/python scripts/utility_personalization_judge.py

  # execute
  DRA_ALLOW_EXTERNAL_API=1 open_deep_research/.venv/bin/python \
    scripts/utility_personalization_judge.py --execute --resume
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(
                key.strip(), value.strip().strip('"').strip("'")
            )

from scripts.dry_run import _load_persona  # noqa: E402
from scripts.llm_matcher import format_persona  # noqa: E402

ALLOW_ENV = "DRA_ALLOW_EXTERNAL_API"
MANIFEST_PATH = ROOT / "manifest.json"
CONFIRMATORY_DIR = ROOT / "runs" / "confirmatory"
MATCH_DIR = ROOT / "runs" / "confirmatory" / "matches_hardneg_v1"
DEFAULT_OUT = ROOT / "runs" / "confirmatory" / "utility_judge_gpt4omini"
DEFAULT_MODEL = "gpt-4o-mini"

# v1 (legacy): often collapsed content==presentation on all reports.
SYSTEM_PROMPT_V1 = (
    "You evaluate whether a long-form research report is personalized to a "
    "specific user profile. Score only personalization quality, not factuality. "
    "Return scores via the submit_personalization_scores tool."
)

# v2: anti-ceiling + forced independent axes + separate evidence.
SYSTEM_PROMPT_V2 = (
    "You evaluate personalization utility of a long-form research report for "
    "ONE target user profile. Score personalization only (not factuality, "
    "not generic writing quality).\n\n"
    "You MUST score TWO independent dimensions:\n"
    "1) content_personalization — WHAT is covered: topics, constraints, "
    "recommendations, tradeoffs, and priorities that match the user's goals, "
    "role, and actionable preferences.\n"
    "2) presentation_personalization — HOW it is written: tone, jargon level, "
    "structure, depth, and framing adapted to the user's background "
    "(occupation, expertise, decision style).\n\n"
    "Scoring rules:\n"
    "- Use the full 1–5 range. Reserve 5 for exceptional personalization; "
    "most reports should land in 2–4.\n"
    "- Score 1 if the report could apply to almost any user in the domain.\n"
    "- Score the two dimensions SEPARATELY using different evidence. "
    "Identical scores are allowed only when both dimensions truly match; "
    "you must still provide DISTINCT evidence for each.\n"
    "- Do not reward mere presence of generic section headings.\n"
    "Return scores via the submit_personalization_scores tool."
)

SYSTEM_PROMPT = SYSTEM_PROMPT_V2  # default for new runs

JUDGE_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_personalization_scores",
        "description": "Submit independent personalization utility scores.",
        "parameters": {
            "type": "object",
            "properties": {
                "content_personalization": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": (
                        "WHAT is covered for this user. "
                        "1=generic domain content; 3=some user-specific priorities; "
                        "5=strongly tailored recommendations/constraints/topics"
                    ),
                },
                "presentation_personalization": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": (
                        "HOW the report is written for this user. "
                        "1=generic tone/structure; 3=partially adapted depth/style; "
                        "5=clearly adapted to background and decision style"
                    ),
                },
                "content_evidence": {
                    "type": "string",
                    "description": (
                        "1-2 sentences citing report content that supports the "
                        "content score (topics, constraints, recommendations)."
                    ),
                },
                "presentation_evidence": {
                    "type": "string",
                    "description": (
                        "1-2 sentences citing style/structure/depth evidence "
                        "for the presentation score (must differ from content_evidence)."
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": (
                        "Brief overall justification, including why the two "
                        "scores are equal or different."
                    ),
                },
            },
            "required": [
                "content_personalization",
                "presentation_personalization",
                "content_evidence",
                "presentation_evidence",
                "reasoning",
            ],
        },
    },
}


def _load_env_fallback() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _find_source_artifact(run_id: str) -> Path:
    summary = CONFIRMATORY_DIR / f"{run_id}_summary.json"
    if summary.exists():
        payload = json.loads(summary.read_text(encoding="utf-8"))
        candidate = Path(payload["artifact_path"])
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.exists():
            return candidate
    for suffix in ("_artifacts.json", "_tokens.json"):
        path = CONFIRMATORY_DIR / f"{run_id}{suffix}"
        if path.exists():
            return path
    raise FileNotFoundError(f"No artifact for {run_id}")


def _truncate(text: str, max_chars: int = 10000) -> str:
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.75)
    tail = max_chars - head
    return text[:head] + "\n\n[...]\n\n" + text[-tail:]


def _task_and_query(run_id: str, manifest: dict[str, Any]) -> tuple[str, str, str]:
    m = re.match(r"pilot_task(\d+)_(User\d+)_seed(\d+)$", run_id)
    if not m:
        raise ValueError(f"bad run_id {run_id}")
    taskid = int(m.group(1))
    gt = m.group(2)
    for task in manifest["pdr_bench"]["confirmatory"]:
        if int(task["taskid"]) != taskid:
            continue
        exp = next(e for e in task["experiments"] if e["gt_userid"] == gt)
        query = exp.get("query") or task["task"]
        # strip persona block if embedded
        if "User Persona:" in query:
            query = query.split("User Persona:")[0].replace("User Task:", "").strip()
        return task["domain"], task["task"], query
    raise KeyError(run_id)


def _load_write_correct(run_id: str) -> dict[str, Any]:
    path = MATCH_DIR / f"{run_id}_match.json"
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for row in rows:
        out[row["stage"]] = {
            "correct": bool(row["correct"]),
            "predicted_userid": row.get("predicted_userid"),
        }
    # recovery pattern
    plan = out.get("plan", {}).get("correct")
    search = out.get("search", {}).get("correct")
    write = out.get("write", {}).get("correct")
    if plan is True and search is False and write is True:
        pattern = "recovered"
    elif plan is True and search is False and write is False:
        pattern = "non_recovered"
    elif plan and search and write:
        pattern = "all_correct_prefix"
    elif write:
        pattern = "write_correct_other"
    else:
        pattern = "write_wrong_other"
    out["pattern"] = pattern
    return out


def _build_user_prompt(
    *,
    domain: str,
    task: str,
    persona_text: str,
    report: str,
    rubric_version: str = "v2",
) -> str:
    if rubric_version == "v1":
        tail = (
            "Score how personalized this report is for the target user profile. "
            "Ignore general writing quality except where it reflects personalization. "
            "Call submit_personalization_scores."
        )
    else:
        tail = (
            "Score content and presentation personalization independently for "
            "this target user. Prefer the mid-range unless personalization is "
            "clearly weak (1–2) or exceptional (5). Provide distinct evidence "
            "for each dimension. Call submit_personalization_scores."
        )
    return (
        f"## Domain\n{domain}\n\n"
        f"## User Task\n{task}\n\n"
        f"## Target User Profile\n{persona_text}\n\n"
        f"## Final Research Report\n{_truncate(report)}\n\n"
        f"{tail}"
    )


def _judge_one(
    client: Any,
    model: str,
    system: str,
    user: str,
) -> dict[str, Any]:
    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        tools=[JUDGE_TOOL],
        tool_choice={
            "type": "function",
            "function": {"name": "submit_personalization_scores"},
        },
    )
    latency = time.monotonic() - t0
    msg = resp.choices[0].message
    if not msg.tool_calls:
        raise RuntimeError("Judge returned no tool call")
    args = json.loads(msg.tool_calls[0].function.arguments)
    usage = getattr(resp, "usage", None)
    return {
        "content_personalization": int(args["content_personalization"]),
        "presentation_personalization": int(
            args["presentation_personalization"]
        ),
        "mean_personalization": round(
            (
                int(args["content_personalization"])
                + int(args["presentation_personalization"])
            )
            / 2.0,
            3,
        ),
        "content_evidence": args.get("content_evidence", ""),
        "presentation_evidence": args.get("presentation_evidence", ""),
        "reasoning": args.get("reasoning", ""),
        "latency_sec": round(latency, 3),
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "api_response_id": getattr(resp, "id", None),
        "model": model,
    }


def _task_bootstrap_delta(
    completed: list[dict[str, Any]],
    score_key: str = "mean_personalization",
    reps: int = 2000,
    seed: int = 42,
) -> list[float]:
    import random
    from collections import defaultdict

    by_task: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in completed:
        by_task[r.get("taskid")].append(r)
    taskids = [t for t in by_task if t is not None]
    if not taskids:
        return [float("nan"), float("nan")]
    rng = random.Random(seed)
    vals: list[float] = []
    for _ in range(reps):
        sampled: list[dict[str, Any]] = []
        for tid in rng.choices(taskids, k=len(taskids)):
            sampled.extend(by_task[tid])
        correct = [
            float(r[score_key])
            for r in sampled
            if r.get("write_correct") and score_key in r
        ]
        wrong = [
            float(r[score_key])
            for r in sampled
            if (not r.get("write_correct")) and score_key in r
        ]
        if not correct or not wrong:
            continue
        vals.append(sum(correct) / len(correct) - sum(wrong) / len(wrong))
    if not vals:
        return [float("nan"), float("nan")]
    ordered = sorted(vals)
    lo = ordered[int(0.025 * (len(ordered) - 1))]
    hi = ordered[int(0.975 * (len(ordered) - 1))]
    return [round(lo, 3), round(hi, 3)]


def main(argv: list[str] | None = None) -> int:
    _load_env_fallback()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None, help="Filter seed")
    parser.add_argument(
        "--rubric-version",
        choices=["v1", "v2"],
        default="v2",
        help="v2 forces independent content/presentation evidence (default)",
    )
    args = parser.parse_args(argv)

    system_prompt = SYSTEM_PROMPT_V1 if args.rubric_version == "v1" else SYSTEM_PROMPT_V2

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    summaries = sorted(CONFIRMATORY_DIR.glob("pilot_*_summary.json"))
    run_ids = [p.name.replace("_summary.json", "") for p in summaries]
    if args.seed is not None:
        run_ids = [r for r in run_ids if r.endswith(f"_seed{args.seed}")]
    if args.limit is not None:
        run_ids = run_ids[: args.limit]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    client = None
    if args.execute:
        if os.environ.get(ALLOW_ENV) != "1":
            raise RuntimeError(f"Set {ALLOW_ENV}=1 for external API calls")
        from openai import OpenAI

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    rows: list[dict[str, Any]] = []
    planned_chars = 0
    for run_id in run_ids:
        out_path = args.output_dir / f"{run_id}_utility.json"
        if args.resume and out_path.exists():
            rows.append(json.loads(out_path.read_text(encoding="utf-8")))
            print(f"SKIP {run_id}", flush=True)
            continue

        artifact_path = _find_source_artifact(run_id)
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        gt = artifact["execution_config"]["gt_userid"]
        domain, task, _query = _task_and_query(run_id, manifest)
        persona_text = format_persona(_load_persona(gt))
        report = artifact.get("final_report") or ""
        user_prompt = _build_user_prompt(
            domain=domain,
            task=task,
            persona_text=persona_text,
            report=report,
            rubric_version=args.rubric_version,
        )
        planned_chars += len(system_prompt) + len(user_prompt)
        stage_attr = _load_write_correct(run_id)
        base = {
            "run_id": run_id,
            "gt_userid": gt,
            "domain": domain,
            "taskid": artifact["execution_config"].get("taskid"),
            "seed": artifact["execution_config"].get("generation_seed"),
            "prompt_chars": len(system_prompt) + len(user_prompt),
            "report_chars": len(report),
            "stage_attribution": stage_attr,
            "write_correct": stage_attr.get("write", {}).get("correct"),
            "pattern": stage_attr.get("pattern"),
            "rubric_version": args.rubric_version,
        }

        if not args.execute:
            rows.append({**base, "status": "planned"})
            print(f"PLAN {run_id} chars={base['prompt_chars']}", flush=True)
            continue

        print(f"JUDGE {run_id} ...", flush=True)
        try:
            scores = _judge_one(client, args.model, system_prompt, user_prompt)
            row = {**base, "status": "completed", **scores}
            out_path.write_text(
                json.dumps(row, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            rows.append(row)
            print(
                f"  content={scores['content_personalization']} "
                f"presentation={scores['presentation_personalization']} "
                f"write_correct={base['write_correct']}",
                flush=True,
            )
        except Exception as exc:
            row = {**base, "status": "error", "error": str(exc)}
            rows.append(row)
            print(f"  ERROR {exc}", flush=True)

    # Aggregate correlation-style summary
    completed = [r for r in rows if r.get("status") == "completed"]
    summary: dict[str, Any] = {
        "model": args.model,
        "rubric_version": args.rubric_version,
        "execute": args.execute,
        "n_runs": len(run_ids),
        "n_completed": len(completed),
        "planned_prompt_chars": planned_chars,
        "external_api_calls": len(completed) if args.execute else 0,
    }
    if completed:
        def mean(xs: list[float]) -> float:
            return round(sum(xs) / len(xs), 3) if xs else float("nan")

        contents = [r["content_personalization"] for r in completed]
        presentations = [r["presentation_personalization"] for r in completed]
        summary["overall_mean_content"] = mean(contents)
        summary["overall_mean_presentation"] = mean(presentations)
        summary["overall_mean"] = mean(
            [r["mean_personalization"] for r in completed]
        )
        n_identical = sum(1 for c, p in zip(contents, presentations) if c == p)
        summary["n_identical_content_presentation"] = n_identical
        summary["frac_identical_content_presentation"] = round(
            n_identical / len(completed), 3
        )
        from collections import Counter

        summary["content_score_distribution"] = dict(Counter(contents))
        summary["presentation_score_distribution"] = dict(Counter(presentations))
        summary["score_distribution"] = dict(
            Counter(int(round(r["mean_personalization"])) for r in completed)
        )

        by_write = {"correct": [], "wrong": []}
        for r in completed:
            key = "correct" if r.get("write_correct") else "wrong"
            by_write[key].append(r["mean_personalization"])
        summary["mean_by_write_correct"] = {
            k: {"n": len(v), "mean": mean(v)} for k, v in by_write.items()
        }

        by_pattern: dict[str, list[float]] = {}
        for r in completed:
            by_pattern.setdefault(r.get("pattern") or "unknown", []).append(
                r["mean_personalization"]
            )
        summary["mean_by_pattern"] = {
            k: {"n": len(v), "mean": mean(v)} for k, v in by_pattern.items()
        }

        # Point-biserial style: difference write correct - wrong
        if by_write["correct"] and by_write["wrong"]:
            summary["delta_write_correct_minus_wrong"] = round(
                mean(by_write["correct"]) - mean(by_write["wrong"]), 3
            )
            summary["delta_bootstrap_95ci"] = _task_bootstrap_delta(completed)

        # Simple Pearson between mean_personalization and write_correct
        xs = [1.0 if r.get("write_correct") else 0.0 for r in completed]
        ys = [float(r["mean_personalization"]) for r in completed]
        if len(xs) >= 3:
            mx = sum(xs) / len(xs)
            my = sum(ys) / len(ys)
            num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            denx = sum((x - mx) ** 2 for x in xs) ** 0.5
            deny = sum((y - my) ** 2 for y in ys) ** 0.5
            summary["pearson_r_write_correct_vs_mean"] = (
                round(num / (denx * deny), 4) if denx and deny else None
            )

        # Seed split
        by_seed: dict[Any, dict[str, list[float]]] = {}
        for r in completed:
            s = r.get("seed")
            by_seed.setdefault(s, {"correct": [], "wrong": []})
            key = "correct" if r.get("write_correct") else "wrong"
            by_seed[s][key].append(r["mean_personalization"])
        summary["delta_by_seed"] = {
            str(s): {
                "write_correct_n": len(v["correct"]),
                "write_wrong_n": len(v["wrong"]),
                "delta": (
                    round(mean(v["correct"]) - mean(v["wrong"]), 3)
                    if v["correct"] and v["wrong"]
                    else None
                ),
            }
            for s, v in sorted(by_seed.items(), key=lambda x: str(x[0]))
        }

        # Stage correctness deltas
        stage_deltas: dict[str, Any] = {}
        for stage in ("plan", "search", "compress", "write"):
            corr, wrong = [], []
            for r in completed:
                st = (r.get("stage_attribution") or {}).get(stage) or {}
                if "correct" not in st:
                    continue
                (corr if st["correct"] else wrong).append(r["mean_personalization"])
            if corr and wrong:
                stage_deltas[stage] = {
                    "correct_mean": mean(corr),
                    "wrong_mean": mean(wrong),
                    "correct_n": len(corr),
                    "wrong_n": len(wrong),
                    "delta": round(mean(corr) - mean(wrong), 3),
                }
        summary["mean_by_stage_correct"] = stage_deltas

    summary_path = args.output_dir / "utility_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if not any(r.get("status") == "error" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
