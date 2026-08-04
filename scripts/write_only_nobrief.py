"""Writing-only no-brief ablation.

Re-generate final reports from frozen confirmatory artifacts while removing
the Planning research brief from the Writing prompt. Plan/Search/Compress are
not re-run (no Serper cost).

Usage:
  # plan only
  open_deep_research/.venv/bin/python scripts/write_only_nobrief.py --n 15

  # execute Gemini write-only regeneration
  DRA_ALLOW_EXTERNAL_API=1 open_deep_research/.venv/bin/python \
    scripts/write_only_nobrief.py --n 15 --execute
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_ODR_SRC = str(ROOT / "open_deep_research" / "src")
if _ODR_SRC not in sys.path:
    sys.path.insert(0, _ODR_SRC)

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    # Minimal .env loader when python-dotenv is unavailable.
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

from scripts.dry_run import _build_user_message, _load_persona  # noqa: E402

ALLOW_ENV = "DRA_ALLOW_EXTERNAL_API"
MANIFEST_PATH = ROOT / "manifest.json"
CONFIRMATORY_DIR = ROOT / "runs" / "confirmatory"
DEFAULT_OUT = ROOT / "runs" / "ablation" / "nobrief_writeonly"
MODEL_NAME = "google_genai:gemini-3.6-flash"

NO_BRIEF_PROMPT = """Based on all the research conducted, create a comprehensive, well-structured answer to the user's research needs.

NOTE: No separate research brief is provided. Rely on the user messages and the research findings below.

For context, here are the messages so far:
<Messages>
{messages}
</Messages>
CRITICAL: Make sure the answer is written in the same language as the human messages!
For example, if the user's messages are in English, then MAKE SURE you write your response in English. If the user's messages are in Chinese, then MAKE SURE you write your entire response in Chinese.
This is critical. The user will only understand the answer if it is written in the same language as their input message.

Today's date is {date}.

Here are the findings from the research that you conducted:
<Findings>
{findings}
</Findings>

Please create a detailed answer that:
1. Is well-organized with proper headings (# for title, ## for sections, ### for subsections)
2. Includes specific facts and insights from the research
3. References relevant sources using [Title](URL) format
4. Provides a balanced, thorough analysis. Be as comprehensive as possible, and include all information that is relevant to the overall research question.
5. Includes a "Sources" section at the end with all referenced links

For each section of the report, do the following:
- Use simple, clear language
- Use ## for section title (Markdown format) for each section of the report
- Do NOT ever refer to yourself as the writer of the report.
- Do not say what you are doing in the report. Just write the report without any commentary from yourself.
- Each section should be as long as necessary to deeply answer the question with the information you have gathered.
- Use bullet points to list out information when appropriate, but by default, write in paragraph form.

Format the report in clear markdown with proper structure and include source references where appropriate.

<Citation Rules>
- Assign each unique URL a single citation number in your text
- End with a Sources section listing those references
</Citation Rules>
"""


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
    """Resolve frozen confirmatory artifact path for a pilot run_id."""
    summary = CONFIRMATORY_DIR / f"{run_id}_summary.json"
    if summary.exists():
        payload = json.loads(summary.read_text(encoding="utf-8"))
        candidate = Path(payload["artifact_path"])
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.exists():
            return candidate
    # Fallback: common naming variants
    for suffix in ("_artifacts.json", "_tokens.json"):
        path = CONFIRMATORY_DIR / f"{run_id}{suffix}"
        if path.exists():
            return path
    # Last resort: any large JSON matching run_id with research_brief
    for path in CONFIRMATORY_DIR.glob(f"{run_id}*.json"):
        if path.name.endswith("_summary.json") or path.name.endswith("_match.json"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "research_brief" in data and "final_report" in data:
            return path
    raise FileNotFoundError(f"No source artifact for {run_id}")


def _list_seed0_run_ids() -> list[str]:
    run_ids: list[str] = []
    for path in sorted(CONFIRMATORY_DIR.glob("pilot_*_seed0_summary.json")):
        run_ids.append(path.name.replace("_summary.json", ""))
    return run_ids


def _select_run_ids(n: int, seed: int = 0) -> list[str]:
    """Select up to n seed-0 runs, preferring complete task groups of 3."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    available = set(_list_seed0_run_ids())
    selected: list[str] = []
    for task in manifest["pdr_bench"]["confirmatory"]:
        group = [
            f"pilot_task{task['taskid']}_{uid}_seed{seed}"
            for uid in task["personas_n3"]
        ]
        if not all(run_id in available for run_id in group):
            continue
        if len(selected) + 3 > n and len(selected) > 0:
            # fill remainder with whole groups only when possible
            if len(selected) >= n:
                break
            if len(selected) + 3 > n:
                break
        selected.extend(group)
        if len(selected) >= n:
            break
    if len(selected) < n:
        # top up with any remaining seed0 runs
        for run_id in _list_seed0_run_ids():
            if run_id not in selected:
                selected.append(run_id)
            if len(selected) >= n:
                break
    return selected[:n]


def _findings_from_artifact(artifact: dict[str, Any]) -> str:
    parts: list[str] = []
    for block in artifact.get("compressed_research") or []:
        topic = block.get("topic_text") or block.get("topic_id") or ""
        content = block.get("compressed_research") or ""
        parts.append(f"## {topic}\n{content}".strip())
    text = "\n\n".join(parts).strip()
    if not text:
        raise ValueError("compressed_research empty; cannot rebuild findings")
    return text


def _messages_from_manifest(run_id: str, manifest: dict[str, Any]) -> str:
    m = re.match(r"pilot_task(\d+)_(User\d+)_seed(\d+)$", run_id)
    if not m:
        raise ValueError(f"Cannot parse run_id: {run_id}")
    taskid = int(m.group(1))
    gt_userid = m.group(2)
    for task in manifest["pdr_bench"]["confirmatory"]:
        if int(task["taskid"]) != taskid:
            continue
        experiment = next(
            exp for exp in task["experiments"] if exp["gt_userid"] == gt_userid
        )
        persona = _load_persona(gt_userid)
        return _build_user_message(task, experiment, persona)
    raise KeyError(f"task/persona not found for {run_id}")


def _build_prompt(
    *,
    messages: str,
    findings: str,
    date: str,
    condition: str,
    research_brief: str,
) -> str:
    if condition == "nobrief":
        return NO_BRIEF_PROMPT.format(
            messages=messages, findings=findings, date=date
        )
    if condition in ("full_control", "otherbrief"):
        # full_control: own Planning brief; otherbrief: donor persona brief.
        return (
            "Based on all the research conducted, create a comprehensive, "
            "well-structured answer to the overall research brief:\n"
            f"<Research Brief>\n{research_brief}\n</Research Brief>\n\n"
            "For more context, here is all of the messages so far. Focus on the "
            "research brief above, but consider these messages as well for more context.\n"
            f"<Messages>\n{messages}\n</Messages>\n"
            "CRITICAL: Make sure the answer is written in the same language as the human messages!\n"
            f"Today's date is {date}.\n\n"
            "Here are the findings from the research that you conducted:\n"
            f"<Findings>\n{findings}\n</Findings>\n\n"
            "Please create a detailed answer to the overall research brief that:\n"
            "1. Is well-organized with proper headings\n"
            "2. Includes specific facts and insights from the research\n"
            "3. References relevant sources using [Title](URL) format\n"
            "4. Provides a balanced, thorough analysis\n"
            "5. Includes a Sources section at the end\n"
            "Do NOT refer to yourself as the writer. Write a professional report."
        )
    raise ValueError(f"Unknown condition: {condition}")


def _donor_brief_for_run(
    source_run_id: str, manifest: dict[str, Any]
) -> tuple[str, str]:
    """Pick another persona's research brief from the same task group.

    Donor = cyclic next userid in the confirmatory personas_n3 list.
    Returns (donor_run_id, research_brief).
    """
    m = re.match(r"pilot_task(\d+)_(User\d+)_seed(\d+)$", source_run_id)
    if not m:
        raise ValueError(source_run_id)
    taskid, gt, seed = int(m.group(1)), m.group(2), int(m.group(3))
    for task in manifest["pdr_bench"]["confirmatory"]:
        if int(task["taskid"]) != taskid:
            continue
        group = list(task["personas_n3"])
        if gt not in group:
            raise KeyError(f"{gt} not in personas_n3 for task {taskid}")
        idx = group.index(gt)
        donor = group[(idx + 1) % len(group)]
        donor_run = f"pilot_task{taskid}_{donor}_seed{seed}"
        donor_path = _find_source_artifact(donor_run)
        donor_art = json.loads(donor_path.read_text(encoding="utf-8"))
        brief = donor_art.get("research_brief") or ""
        if not brief.strip():
            raise ValueError(f"empty brief for donor {donor_run}")
        return donor_run, brief
    raise KeyError(f"task {taskid} not found")


def _generate_report(prompt: str, max_tokens: int = 8192) -> tuple[str, dict[str, Any]]:
    from langchain.chat_models import init_chat_model
    from langchain_core.messages import HumanMessage

    model = init_chat_model(
        model=MODEL_NAME,
        temperature=0,
        max_tokens=max_tokens,
    )
    t0 = time.monotonic()
    response = model.invoke([HumanMessage(content=prompt)])
    latency = time.monotonic() - t0
    content = response.content
    if isinstance(content, list):
        # Gemini sometimes returns list of content blocks
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
            else:
                texts.append(str(block))
        content = "".join(texts)
    usage_meta = getattr(response, "usage_metadata", None) or {}
    return str(content), {
        "latency_sec": round(latency, 3),
        "usage_metadata": dict(usage_meta) if usage_meta else {},
        "model": MODEL_NAME,
    }


def _out_run_id(source_run_id: str, condition: str) -> str:
    return source_run_id.replace("pilot_", f"ablation_{condition}_", 1)


def process_one(
    source_run_id: str,
    *,
    condition: str,
    output_dir: Path,
    execute: bool,
    resume: bool,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    out_run_id = _out_run_id(source_run_id, condition)
    out_path = output_dir / f"{out_run_id}_artifacts.json"
    summary_path = output_dir / f"{out_run_id}_summary.json"

    if resume and out_path.exists() and summary_path.exists():
        return {
            "status": "skipped_exists",
            "source_run_id": source_run_id,
            "out_run_id": out_run_id,
            "artifact_path": str(out_path),
        }

    source_path = _find_source_artifact(source_run_id)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    findings = _findings_from_artifact(source)
    messages = _messages_from_manifest(source_run_id, manifest)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    donor_run_id = None
    if condition == "otherbrief":
        donor_run_id, research_brief = _donor_brief_for_run(
            source_run_id, manifest
        )
    else:
        research_brief = source.get("research_brief") or ""
    prompt = _build_prompt(
        messages=messages,
        findings=findings,
        date=date,
        condition=condition,
        research_brief=research_brief,
    )
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    plan = {
        "status": "planned",
        "source_run_id": source_run_id,
        "out_run_id": out_run_id,
        "condition": condition,
        "source_artifact": str(source_path),
        "prompt_chars": len(prompt),
        "prompt_sha256": prompt_sha,
        "findings_chars": len(findings),
        "messages_chars": len(messages),
        "brief_chars": len(research_brief),
        "donor_run_id": donor_run_id,
        "original_report_chars": len(source.get("final_report") or ""),
    }

    if not execute:
        return plan

    if os.environ.get(ALLOW_ENV) != "1":
        raise RuntimeError(f"Set {ALLOW_ENV}=1 to execute external Gemini calls")

    report, gen_meta = _generate_report(prompt)
    artifact = dict(source)
    artifact["run_id"] = out_run_id
    artifact["final_report"] = report
    artifact["execution_config"] = {
        **(source.get("execution_config") or {}),
        "persona_condition": condition,
        "write_only_ablation": True,
        "source_run_id": source_run_id,
        "brief_injected": condition != "nobrief",
        "brief_source": (
            "none"
            if condition == "nobrief"
            else ("donor" if condition == "otherbrief" else "own")
        ),
        "donor_run_id": donor_run_id,
        "prompt_sha256": prompt_sha,
        "write_model": MODEL_NAME,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    # Keep original brief in artifact for audit; Writing prompt may omit it
    # (nobrief) or replace it with a donor brief (otherbrief).
    artifact["write_only_meta"] = {
        "condition": condition,
        "source_run_id": source_run_id,
        "donor_run_id": donor_run_id,
        "prompt_sha256": prompt_sha,
        "prompt_chars": len(prompt),
        "generation": gen_meta,
        "original_final_report_sha256": hashlib.sha256(
            (source.get("final_report") or "").encode("utf-8")
        ).hexdigest(),
        "new_final_report_sha256": hashlib.sha256(
            report.encode("utf-8")
        ).hexdigest(),
        "new_final_report_chars": len(report),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        **plan,
        "status": "completed",
        "artifact_path": str(out_path),
        "new_report_chars": len(report),
        "generation": gen_meta,
        "schema_valid": bool(report.strip()),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    _load_env_fallback()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=15, help="Number of seed-0 reports")
    parser.add_argument(
        "--condition",
        choices=["nobrief", "full_control", "otherbrief"],
        default="nobrief",
        help=(
            "nobrief removes Planning brief; full_control re-injects own brief; "
            "otherbrief injects another persona's brief from the same task group"
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--run-ids",
        nargs="*",
        default=None,
        help="Optional explicit pilot_ run IDs",
    )
    args = parser.parse_args(argv)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    run_ids = args.run_ids or _select_run_ids(args.n, seed=0)

    results = []
    for run_id in run_ids:
        print(f"[{args.condition}] {run_id} ...", flush=True)
        try:
            row = process_one(
                run_id,
                condition=args.condition,
                output_dir=args.output_dir,
                execute=args.execute,
                resume=args.resume,
                manifest=manifest,
            )
            results.append(row)
            status = row.get("status")
            print(
                f"  -> {status} prompt_chars={row.get('prompt_chars')} "
                f"new_chars={row.get('new_report_chars')}",
                flush=True,
            )
        except Exception as exc:
            print(f"  ERROR: {exc}", flush=True)
            results.append(
                {
                    "status": "error",
                    "source_run_id": run_id,
                    "error": str(exc),
                }
            )

    batch_summary = {
        "condition": args.condition,
        "execute": args.execute,
        "n_requested": args.n,
        "n_selected": len(run_ids),
        "run_ids": run_ids,
        "results": results,
        "external_api_calls": sum(
            1 for row in results if row.get("status") == "completed"
        ),
        "planned_prompt_chars": sum(
            int(row.get("prompt_chars") or 0) for row in results
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_summary = args.output_dir / f"batch_{args.condition}_summary.json"
    out_summary.write_text(
        json.dumps(batch_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "summary_path": str(out_summary),
        "completed": batch_summary["external_api_calls"],
        "errors": sum(1 for row in results if row.get("status") == "error"),
        "planned_prompt_chars": batch_summary["planned_prompt_chars"],
    }, indent=2))
    return 0 if not any(r.get("status") == "error" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
