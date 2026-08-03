"""N=2 and N=5 candidate-set sensitivity matching via Solar-pro.

Reads the frozen sensitivity plan from provenance/candidate_sensitivity_plan.json,
re-runs the Solar matcher with N=2 and N=5 candidate sets (instead of the
default N=3), and writes per-report match files to:
  runs/confirmatory/matches_sensitivity_n2/
  runs/confirmatory/matches_sensitivity_n5/

No new artifact generation needed — uses existing artifact files.

Usage:
    python scripts/run_sensitivity_matching.py [--n 2] [--n 5] [--dry-run] [--resume]
    python scripts/run_sensitivity_matching.py           # runs both N=2 and N=5
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.llm_matcher import (
    STAGES,
    SYSTEM_PROMPT,
    StageMatch,
    SolarMatcher,
    compute_accuracy,
    deterministic_candidate_order,
    format_persona,
    load_personas,
    serialize_artifact,
)

LABELS_BY_N = {
    2: ["A", "B"],
    3: ["A", "B", "C"],
    5: ["A", "B", "C", "D", "E"],
}

LABELS_STR = {
    2: "A or B",
    3: "A, B, or C",
    5: "A, B, C, D, or E",
}


def build_attribution_tool(n: int) -> dict:
    labels = LABELS_BY_N[n]
    return {
        "type": "function",
        "function": {
            "name": "submit_attribution",
            "description": "Submit the attribution decision and reasoning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "predicted_label": {
                        "type": "string",
                        "enum": labels,
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


def build_user_prompt_n(
    stage: str, artifact_text: str, labeled_personas: list[tuple[str, str]], n: int
) -> str:
    stage_label = {
        "plan": "Research Planning Brief",
        "search": "Search Queries and Retrieved Sources",
        "compress": "Compressed Research Summaries",
        "write": "Final Research Report (excerpt)",
    }[stage]
    parts = [f"## {stage_label}\n\n{artifact_text}\n\n## Candidate User Profiles\n"]
    for label, text in labeled_personas:
        parts.append(f"### Candidate {label}\n{text}\n")
    label_str = LABELS_STR[n]
    parts.append(
        f"\nWhich candidate profile ({label_str}) best matches the perspective, "
        "priorities, and content framing of the document above? "
        "Call submit_attribution."
    )
    return "\n".join(parts)


def match_one_stage_n(
    run_id: str,
    stage: str,
    artifacts: dict,
    gt_userid: str,
    candidate_userids: list[str],
    personas_by_id: dict,
    matcher: "SolarMatcher | None",
    n: int,
    shuffle_seed: int = 42,
    dry_run: bool = False,
) -> StageMatch:
    from scripts.llm_matcher import STAGE_CHAR_CAPS
    artifact_text = serialize_artifact(artifacts, stage)
    labels = LABELS_BY_N[n]

    shuffled = deterministic_candidate_order(run_id, stage, candidate_userids, shuffle_seed)
    assert len(shuffled) == n, f"Expected {n} candidates, got {len(shuffled)}"

    active_labels = labels[:n]
    labeled_personas = [
        (label, format_persona(personas_by_id[uid]))
        for label, uid in zip(active_labels, shuffled)
    ]

    user_prompt = build_user_prompt_n(stage, artifact_text, labeled_personas, n)
    prompt_chars = len(SYSTEM_PROMPT) + len(user_prompt)

    if dry_run or matcher is None:
        print(f"  DRY {stage}: candidates={list(zip(active_labels, shuffled))}")
        return StageMatch(
            run_id=run_id, stage=stage, gt_userid=gt_userid,
            candidate_userids=candidate_userids, shuffled_order=shuffled,
            predicted_label="?", predicted_userid="?", correct=False,
            reasoning="DRY_RUN", model="none", prompt_chars=prompt_chars,
            latency_sec=0.0, shuffle_seed=shuffle_seed, artifact_view="full",
        )

    tool = build_attribution_tool(n)
    t0 = time.monotonic()

    import os
    from openai import OpenAI
    client = OpenAI(
        api_key=os.environ.get("UPSTAGE_API_KEY"),
        base_url="https://api.upstage.ai/v1",
    )
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="solar-pro",
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": "submit_attribution"}},
            )
            break
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  retry {attempt+1}: {e}")
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError("All retries failed")

    latency = time.monotonic() - t0
    msg = resp.choices[0].message
    tool_call = msg.tool_calls[0] if msg.tool_calls else None
    if tool_call is None:
        raise ValueError(f"No tool call in response for {run_id}/{stage}")

    args = json.loads(tool_call.function.arguments)
    pred_label = args["predicted_label"]
    reasoning = args.get("reasoning", "")
    label_to_uid = dict(zip(active_labels, shuffled))
    pred_userid = label_to_uid.get(pred_label, "UNKNOWN")

    status = "✓" if pred_userid == gt_userid else "✗"
    print(f"  {status} {stage:8s}  pred={pred_userid}  gt={gt_userid}  {latency:.1f}s")

    return StageMatch(
        run_id=run_id, stage=stage, gt_userid=gt_userid,
        candidate_userids=candidate_userids, shuffled_order=shuffled,
        predicted_label=pred_label, predicted_userid=pred_userid,
        correct=(pred_userid == gt_userid),
        reasoning=reasoning, model="solar-pro",
        prompt_chars=prompt_chars, latency_sec=round(latency, 2),
        shuffle_seed=shuffle_seed, artifact_view="full",
    )


def run_sensitivity(
    n: int,
    plan: dict,
    artifact_dir: Path,
    output_dir: Path,
    personas_by_id: dict,
    matcher,
    dry_run: bool,
    resume: bool,
    seed_filter: int | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_map = {(row["taskid"], row["gt_userid"]): row for row in plan["rows"]}
    all_results: list[StageMatch] = []
    errors = 0

    artifact_paths = sorted(artifact_dir.glob("*_artifacts.json"))
    if seed_filter is not None:
        artifact_paths = [p for p in artifact_paths if p.name.endswith(f"_seed{seed_filter}_artifacts.json")]

    total = len(artifact_paths)
    print(f"\n=== N={n} sensitivity — {total} artifacts ===")
    for i, artifact_path in enumerate(artifact_paths, 1):
        run_id = artifact_path.stem.replace("_artifacts", "")
        out_path = output_dir / f"{run_id}_match.json"
        if resume and out_path.exists():
            print(f"SKIP {run_id}")
            all_results.extend(StageMatch(**r) for r in json.loads(out_path.read_text()))
            continue

        # Parse taskid and gt_userid from run_id
        parts = run_id.split("_")
        task_token = next((p for p in parts if p.startswith("task")), None)
        user_token = next((p for p in parts if p.startswith("User")), None)
        if task_token is None or user_token is None:
            print(f"SKIP {run_id}: cannot parse")
            continue
        taskid = int(task_token[4:])
        gt_userid = user_token

        plan_row = plan_map.get((taskid, gt_userid))
        if plan_row is None:
            print(f"SKIP {run_id}: not in sensitivity plan")
            continue

        candidates = plan_row["candidate_sets"][str(n)]
        assert gt_userid in candidates, f"GT not in candidates: {gt_userid} not in {candidates}"

        print(f"\n[{i}/{total}] {run_id}  candidates(N={n})={candidates}")
        with open(artifact_path) as f:
            artifacts = json.load(f)

        results = []
        for stage in STAGES:
            try:
                result = match_one_stage_n(
                    run_id=run_id, stage=stage, artifacts=artifacts,
                    gt_userid=gt_userid, candidate_userids=candidates,
                    personas_by_id=personas_by_id, matcher=matcher,
                    n=n, dry_run=dry_run,
                )
                results.append(result)
            except Exception as e:
                print(f"  ERROR {stage}: {e}")
                errors += 1

        if not dry_run:
            out_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
        all_results.extend(results)

    if all_results and not dry_run:
        acc = compute_accuracy(all_results)
        chance = 1 / n
        print(f"\n--- N={n} Accuracy (chance={chance:.3f}) ---")
        for stage in STAGES:
            val = acc.get(stage, float("nan"))
            print(f"  {stage:10s}: {val:.3f}")
        print(f"  macro_avg  : {acc['macro_avg']:.3f}")
        summary = {
            "n": n,
            "chance": round(chance, 4),
            "accuracy": acc,
            "model": "solar-pro",
            "reports": len(artifact_paths),
            "errors": errors,
        }
        (output_dir / "match_accuracy_summary.json").write_text(
            json.dumps(summary, indent=2)
        )
        print(f"Summary -> {output_dir}/match_accuracy_summary.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, choices=[2, 5], action="append",
                        help="Candidate set size (default: both 2 and 5)")
    parser.add_argument("--artifact-dir", type=Path,
                        default=ROOT / "runs/confirmatory")
    parser.add_argument("--output-base", type=Path,
                        default=ROOT / "runs/confirmatory")
    parser.add_argument("--plan", type=Path,
                        default=ROOT / "provenance/candidate_sensitivity_plan.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed", type=int, default=None, help="Only run one seed (0 or 1)")
    args = parser.parse_args()

    ns = args.n if args.n else [2, 5]
    plan = json.loads(args.plan.read_text())
    personas_by_id = load_personas()

    matcher = None if args.dry_run else SolarMatcher()

    for n in ns:
        output_dir = args.output_base / f"matches_sensitivity_n{n}"
        run_sensitivity(
            n=n, plan=plan,
            artifact_dir=args.artifact_dir,
            output_dir=output_dir,
            personas_by_id=personas_by_id,
            matcher=matcher,
            dry_run=args.dry_run,
            resume=args.resume,
            seed_filter=args.seed,
        )


if __name__ == "__main__":
    main()
