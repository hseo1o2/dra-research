"""LLM-based N-way stage-wise persona attribution matcher.

Given a DRA artifact JSON and a candidate persona set, identifies which persona
generated each pipeline stage artifact (plan / search / compress / write).

Primary model: Solar-pro via Upstage API (OpenAI-compatible).
Structured output via tool calling.

Usage:
    # match one run across all 4 stages
    python scripts/llm_matcher.py --run-id pilot_task3_User10_seed0 \
        --artifact-dir runs/pilot --output-dir runs/pilot/matches

    # batch: all artifacts in a directory
    python scripts/llm_matcher.py --batch-dir runs/pilot \
        --output-dir runs/pilot/matches

    # dry-run: print prompts, no API calls
    python scripts/llm_matcher.py --batch-dir runs/pilot --dry-run

    # single stage only
    python scripts/llm_matcher.py --batch-dir runs/pilot --stage plan
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAGES = ["plan", "search", "compress", "write"]

PERSONA_DATA_PATH = ROOT / "data" / "pdr-bench" / "persona_data" / "personas_en.jsonl"
MANIFEST_PATH = ROOT / "manifest.json"

MODEL_PRIMARY = "solar-pro"
MODEL_SECONDARY = "gpt-4o-mini"    # secondary replication check
UPSTAGE_BASE_URL = "https://api.upstage.ai/v1"

# Character caps per stage artifact text sent to matcher
STAGE_CHAR_CAPS = {
    "plan":     4000,
    "search":   3500,
    "compress": 6000,
    "write":    8000,
}

# ---------------------------------------------------------------------------
# Artifact serializers
# ---------------------------------------------------------------------------

def _serialize_plan(artifacts: dict) -> str:
    return artifacts.get("research_brief", "")


def _serialize_search(artifacts: dict, max_chars: int = STAGE_CHAR_CAPS["search"]) -> str:
    lines: list[str] = []
    for call in artifacts.get("search_trace", []):
        if call.get("status") not in ("success", "ok"):
            continue
        query = call.get("query", "")
        topic = call.get("topic_id", "")
        lines.append(f"Query [{topic}]: {query}")
        for src in (call.get("sources") or [])[:3]:
            title = src.get("title", "")
            snippet = src.get("snippet", "")
            lines.append(f"  • {title}: {snippet[:200]}")
    text = "\n".join(lines)
    return text[:max_chars]


def _serialize_compress(artifacts: dict, max_chars: int = STAGE_CHAR_CAPS["compress"]) -> str:
    parts: list[str] = []
    for block in artifacts.get("compressed_research", []):
        topic_id = block.get("topic_id", "")
        content = block.get("compressed_research", "")
        parts.append(f"## {topic_id}\n{content}")
    text = "\n\n".join(parts)
    return text[:max_chars]


def _serialize_write(artifacts: dict, max_chars: int = STAGE_CHAR_CAPS["write"]) -> str:
    report = artifacts.get("final_report", "")
    if len(report) <= max_chars:
        return report
    # keep opening (most persona signal) + tail
    head = int(max_chars * 0.75)
    tail = max_chars - head
    return report[:head] + "\n\n[...]\n\n" + report[-tail:]


_SERIALIZERS = {
    "plan":     _serialize_plan,
    "search":   _serialize_search,
    "compress": _serialize_compress,
    "write":    _serialize_write,
}


def serialize_artifact(artifacts: dict, stage: str) -> str:
    return _SERIALIZERS[stage](artifacts)


# ---------------------------------------------------------------------------
# Persona formatter
# ---------------------------------------------------------------------------

def _flatten_dict(d: Any, prefix: str = "") -> list[str]:
    """Recursively flatten a nested dict into 'Key: value' lines."""
    lines: list[str] = []
    if isinstance(d, dict):
        for k, v in d.items():
            full_key = f"{prefix}{k}" if prefix else k
            lines.extend(_flatten_dict(v, prefix=f"{full_key} > "))
    elif isinstance(d, list):
        for item in d:
            lines.extend(_flatten_dict(item, prefix=prefix))
    else:
        lines.append(f"{prefix.rstrip(' >')}: {d}")
    return lines


# Sections to include in matcher persona text (ordered)
_INCLUDE_SECTIONS = [
    "Basic Attributes",
    "Behavioral Characteristics",
    "Personality Traits",
    "Preferences and Interests",
    "Environment",
]
# Excluded: Health Status, Financial Information (not research-relevant)

def format_persona(persona: dict) -> str:
    """Convert persona dict to flat readable text for the matcher prompt."""
    lines: list[str] = []
    for section in _INCLUDE_SECTIONS:
        content = persona.get(section)
        if content is None:
            continue
        lines.append(f"=== {section} ===")
        lines.extend(_flatten_dict(content))
    return "\n".join(lines)


def load_personas(path: Path = PERSONA_DATA_PATH) -> dict[str, dict]:
    personas: dict[str, dict] = {}
    with open(path) as f:
        for line in f:
            p = json.loads(line)
            personas[p["userid"]] = p
    return personas


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class StageMatch:
    run_id: str
    stage: str
    gt_userid: str
    candidate_userids: list[str]     # original order
    shuffled_order: list[str]        # shuffled (A→shuffled_order[0], etc.)
    predicted_label: str             # A / B / C
    predicted_userid: str            # mapped from label
    correct: bool
    reasoning: str
    model: str
    prompt_chars: int
    latency_sec: float
    shuffle_algorithm: str = "sha256-first-64-bit"
    shuffle_seed: int = 42


# ---------------------------------------------------------------------------
# Solar/OpenAI client wrapper
# ---------------------------------------------------------------------------

MATCH_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_attribution",
        "description": "Submit persona attribution result.",
        "parameters": {
            "type": "object",
            "properties": {
                "predicted_label": {
                    "type": "string",
                    "enum": ["A", "B", "C"],
                    "description": "Label of the best-matching candidate persona.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "2-3 sentence rationale for the choice.",
                },
            },
            "required": ["predicted_label", "reasoning"],
        },
    },
}


SYSTEM_PROMPT = (
    "You are an expert document analyst specializing in user profiling. "
    "Given a document excerpt from a research report and a set of candidate user profiles, "
    "identify which user this document was most likely produced for. "
    "Focus on content priorities, framing, vocabulary, and topic angles "
    "that reflect the user's background, goals, and preferences. "
    "Call submit_attribution with your answer."
)


def _build_user_prompt(stage: str, artifact_text: str, labeled_personas: list[tuple[str, str]]) -> str:
    stage_label = {
        "plan": "Research Planning Brief",
        "search": "Search Queries and Retrieved Sources",
        "compress": "Compressed Research Summaries",
        "write": "Final Research Report (excerpt)",
    }[stage]

    parts = [f"## {stage_label}\n\n{artifact_text}\n\n## Candidate User Profiles\n"]
    for label, text in labeled_personas:
        parts.append(f"### Candidate {label}\n{text}\n")
    parts.append(
        "\nWhich candidate profile (A, B, or C) best matches the perspective, "
        "priorities, and content framing of the document above? "
        "Call submit_attribution."
    )
    return "\n".join(parts)


class SolarMatcher:
    def __init__(self, model: str = MODEL_PRIMARY, base_url: str = UPSTAGE_BASE_URL,
                 api_key: str | None = None):
        from openai import OpenAI
        self.model = model
        is_upstage = "upstage" in base_url
        key = api_key or (
            os.environ.get("UPSTAGE_API_KEY") if is_upstage
            else os.environ.get("OPENAI_API_KEY")
        )
        if not key:
            raise ValueError(
                "Set UPSTAGE_API_KEY (for solar) or OPENAI_API_KEY (for gpt) env var."
            )
        self.client = OpenAI(api_key=key, base_url=base_url)

    def call(self, system: str, user: str, retries: int = 3) -> tuple[str, str]:
        """Returns (predicted_label, reasoning). Raises on failure."""
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    tools=[MATCH_TOOL],
                    tool_choice={"type": "function", "function": {"name": "submit_attribution"}},
                )
                msg = resp.choices[0].message
                if msg.tool_calls:
                    args = json.loads(msg.tool_calls[0].function.arguments)
                    return args["predicted_label"], args.get("reasoning", "")
                # fallback: parse JSON from content
                content = (msg.content or "").strip()
                parsed = json.loads(content)
                return parsed["predicted_label"], parsed.get("reasoning", "")
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"Solar call failed after {retries} retries: {last_err}")


# ---------------------------------------------------------------------------
# Core matching logic
# ---------------------------------------------------------------------------

def match_one_stage(
    run_id: str,
    stage: str,
    artifacts: dict,
    gt_userid: str,
    candidate_userids: list[str],
    personas_by_id: dict[str, dict],
    matcher: SolarMatcher | None,
    shuffle_seed: int = 42,
    dry_run: bool = False,
) -> StageMatch:
    artifact_text = serialize_artifact(artifacts, stage)

    # Shuffle candidate order deterministically per (run_id, stage) to avoid
    # position bias from a fixed global seed. Do not use Python's built-in
    # hash(), which is randomized between interpreter processes.
    seed_material = f"{shuffle_seed}:{run_id}:{stage}".encode("utf-8")
    per_run_seed = int.from_bytes(
        hashlib.sha256(seed_material).digest()[:8],
        byteorder="big",
        signed=False,
    )
    rng = random.Random(per_run_seed)
    shuffled = list(candidate_userids)
    rng.shuffle(shuffled)
    labels = ["A", "B", "C"][: len(shuffled)]

    labeled_personas = [
        (label, format_persona(personas_by_id[uid]))
        for label, uid in zip(labels, shuffled)
    ]

    user_prompt = _build_user_prompt(stage, artifact_text, labeled_personas)
    prompt_chars = len(SYSTEM_PROMPT) + len(user_prompt)

    if dry_run or matcher is None:
        print(f"\n{'='*60}")
        print(f"DRY RUN  run={run_id}  stage={stage}  gt={gt_userid}")
        print(f"Candidates (shuffled): {dict(zip(labels, shuffled))}")
        print(f"Artifact ({stage}, {len(artifact_text)} chars):\n{artifact_text[:300]}...")
        print(f"Prompt total chars: {prompt_chars}")
        return StageMatch(
            run_id=run_id, stage=stage, gt_userid=gt_userid,
            candidate_userids=candidate_userids, shuffled_order=shuffled,
            predicted_label="?", predicted_userid="?", correct=False,
            reasoning="DRY_RUN", model="none", prompt_chars=prompt_chars, latency_sec=0.0,
            shuffle_seed=shuffle_seed,
        )

    t0 = time.monotonic()
    predicted_label, reasoning = matcher.call(SYSTEM_PROMPT, user_prompt)
    latency = time.monotonic() - t0

    label_to_uid = dict(zip(labels, shuffled))
    predicted_userid = label_to_uid.get(predicted_label, "UNKNOWN")

    return StageMatch(
        run_id=run_id, stage=stage, gt_userid=gt_userid,
        candidate_userids=candidate_userids, shuffled_order=shuffled,
        predicted_label=predicted_label, predicted_userid=predicted_userid,
        correct=(predicted_userid == gt_userid),
        reasoning=reasoning, model=matcher.model,
        prompt_chars=prompt_chars, latency_sec=round(latency, 2),
        shuffle_seed=shuffle_seed,
    )


def match_one_run(
    run_id: str,
    artifact_path: Path,
    manifest: dict,
    personas_by_id: dict[str, dict],
    matcher: SolarMatcher | None,
    stages: list[str] = STAGES,
    dry_run: bool = False,
) -> list[StageMatch]:
    with open(artifact_path) as f:
        artifacts = json.load(f)

    # Find task row in manifest to get candidate set and gt_userid
    gt_userid, candidate_userids = _lookup_manifest(run_id, manifest)

    results: list[StageMatch] = []
    for stage in stages:
        artifact_text = serialize_artifact(artifacts, stage)
        if not artifact_text.strip():
            print(f"  SKIP {stage}: empty artifact")
            continue
        result = match_one_stage(
            run_id=run_id, stage=stage, artifacts=artifacts,
            gt_userid=gt_userid, candidate_userids=candidate_userids,
            personas_by_id=personas_by_id, matcher=matcher,
            dry_run=dry_run,
        )
        results.append(result)
        status = "✓" if result.correct else "✗"
        if not dry_run:
            print(f"  {status} {stage:8s}  pred={result.predicted_userid}  gt={gt_userid}  {result.latency_sec:.1f}s")
    return results


def _lookup_manifest(run_id: str, manifest: dict) -> tuple[str, list[str]]:
    """Parse run_id like 'pilot_task3_User10_seed0' to find gt and candidate set."""
    # run_id format: {prefix}_task{taskid}_{gt_userid}_seed{seed}
    parts = run_id.split("_")
    # find taskid and userid
    taskid: int | None = None
    gt_userid: str | None = None
    for i, p in enumerate(parts):
        if p.startswith("task") and p[4:].isdigit():
            taskid = int(p[4:])
        if p.startswith("User") and p[4:].isdigit():
            gt_userid = p

    if taskid is None or gt_userid is None:
        raise ValueError(f"Cannot parse run_id: {run_id}")

    # search all manifest splits
    for split_name in ("dev", "confirmatory"):
        for task_row in manifest.get("pdr_bench", {}).get(split_name, []):
            if task_row["taskid"] == taskid:
                candidates = task_row.get("personas_n3", [])
                if gt_userid in candidates:
                    return gt_userid, candidates

    raise ValueError(f"run_id {run_id} not found in manifest (task={taskid}, gt={gt_userid})")


# ---------------------------------------------------------------------------
# Accuracy computation
# ---------------------------------------------------------------------------

def compute_accuracy(results: list[StageMatch]) -> dict:
    from collections import defaultdict
    stage_correct: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        if r.correct is not False or r.reasoning != "DRY_RUN":
            stage_correct[r.stage].append(r.correct)

    acc: dict[str, float] = {}
    for stage in STAGES:
        vals = stage_correct.get(stage, [])
        acc[stage] = round(sum(vals) / len(vals), 4) if vals else float("nan")

    all_vals = [v for vals in stage_correct.values() for v in vals]
    acc["macro_avg"] = round(sum(all_vals) / len(all_vals), 4) if all_vals else float("nan")
    acc["chance"] = round(1 / 3, 4)
    acc["n"] = len(all_vals) // len(STAGES) if all_vals else 0
    return acc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-based N-way persona attribution matcher")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--run-id", help="Single run ID (e.g. pilot_task3_User10_seed0)")
    src.add_argument("--batch-dir", type=Path, help="Directory containing *_artifacts.json files")

    parser.add_argument("--artifact-dir", type=Path, default=None,
                        help="Directory to find artifacts when using --run-id")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Directory to write match results")
    parser.add_argument("--stage", choices=STAGES + ["all"], default="all",
                        help="Which stage(s) to match (default: all)")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Only match artifacts whose run ID ends with this seed",
    )
    parser.add_argument("--model", default=MODEL_PRIMARY,
                        help=f"Model name (default: {MODEL_PRIMARY})")
    parser.add_argument("--base-url", default=UPSTAGE_BASE_URL,
                        help="API base URL")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print prompts without calling the API")
    parser.add_argument("--resume", action="store_true",
                        help="Skip runs where output file already exists")

    args = parser.parse_args()

    stages = STAGES if args.stage == "all" else [args.stage]
    personas_by_id = load_personas()
    manifest = json.loads(MANIFEST_PATH.read_text())

    matcher: SolarMatcher | None = None
    if not args.dry_run:
        matcher = SolarMatcher(model=args.model, base_url=args.base_url)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Collect artifact paths
    if args.run_id:
        artifact_dir = args.artifact_dir or Path(".")
        artifact_paths = [artifact_dir / f"{args.run_id}_artifacts.json"]
    else:
        artifact_paths = sorted(args.batch_dir.glob("*_artifacts.json"))
        if args.seed is not None:
            suffix = f"_seed{args.seed}_artifacts.json"
            artifact_paths = [
                path for path in artifact_paths if path.name.endswith(suffix)
            ]

    all_results: list[StageMatch] = []

    for artifact_path in artifact_paths:
        run_id = artifact_path.stem.replace("_artifacts", "")
        out_path = args.output_dir / f"{run_id}_match.json"

        if args.resume and out_path.exists():
            print(f"SKIP {run_id} (exists)")
            loaded = [StageMatch(**r) for r in json.loads(out_path.read_text())]
            all_results.extend(loaded)
            continue

        print(f"\n[{run_id}]")
        try:
            results = match_one_run(
                run_id=run_id,
                artifact_path=artifact_path,
                manifest=manifest,
                personas_by_id=personas_by_id,
                matcher=matcher,
                stages=stages,
                dry_run=args.dry_run,
            )
            all_results.extend(results)
            if not args.dry_run:
                out_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
        except Exception as e:
            print(f"  ERROR: {e}")

    if all_results and not args.dry_run:
        acc = compute_accuracy(all_results)
        print("\n--- Attribution Accuracy ---")
        for stage in STAGES:
            val = acc.get(stage, float("nan"))
            bar = "█" * int(val * 20) if val == val else "—"  # nan check
            print(f"  {stage:8s}  Acc={acc.get(stage, float('nan')):.3f}  {bar}")
        print(f"  macro    Acc={acc['macro_avg']:.3f}  (chance={acc['chance']:.3f}, N={acc['n']})")

        summary_path = args.output_dir / "match_accuracy_summary.json"
        summary_path.write_text(json.dumps({
            "accuracy": acc,
            "model": args.model,
            "shuffle": {
                "algorithm": "sha256-first-64-bit",
                "base_seed": 42,
            },
        }, indent=2))
        print(f"\nSummary → {summary_path}")


if __name__ == "__main__":
    main()
