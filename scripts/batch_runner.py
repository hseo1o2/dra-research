"""Batch runner for DRA Personalization experiments.

Runs all experiments for a manifest split sequentially, sharing one
GlobalLedger. Backbone is fixed to gemini-3.6-flash (backbone gate skipped).

Usage:
    # plan only (no API calls)
    python scripts/batch_runner.py --split dev --seed 0

    # execute
    python scripts/batch_runner.py --split dev --seed 0 --execute

    # resume interrupted batch
    python scripts/batch_runner.py --split dev --seed 0 --execute --resume
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

DEFAULT_MANIFEST = ROOT / "manifest.json"
ALLOW_ENV = "DRA_ALLOW_EXTERNAL_API"
MODEL_NAME = "google_genai:gemini-3.6-flash"
TIMEOUT_SEC = 900
MAX_RETRIES = 3
REQUESTS_PER_MINUTE = 4
RETRY_INITIAL_DELAY_SEC = 15


def _iter_experiments(
    manifest: dict[str, Any],
    split: str,
    seed: int,
) -> list[tuple[dict[str, Any], str, int, int]]:
    """Return (task_row, gt_userid, seed, source_query_id) for a split."""
    if split == "dev":
        groups = manifest["pdr_bench"]["dev"]
    elif split == "confirmatory":
        groups = manifest["pdr_bench"]["confirmatory"]
    else:
        raise ValueError(f"Unknown split: {split!r}")
    rows = []
    for task in groups:
        for exp in task["experiments"]:
            rows.append((task, exp["gt_userid"], seed, exp["source_query_id"]))
    return rows


def _run_id(taskid: int, userid: str, seed: int) -> str:
    return f"pilot_task{taskid}_{userid}_seed{seed}"


async def _run_one(
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    manifest_sha256: str,
    task: dict[str, Any],
    gt_userid: str,
    seed: int,
    source_query_id: int,
    run_id: str,
    output_dir: Path,
    ledger: Any,
    use_flex: bool,
) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage

    from open_deep_research.deep_researcher import deep_researcher
    from scripts.dry_run import (
        _build_user_message,
        _frozen_runtime_environment,
        _load_persona,
        _text_sha256,
    )
    from scripts.serper_adapter import SerperAdapter, patch_search, restore_search
    from scripts.tracing_adapter import DRATracer, validate_artifact_file

    persona = _load_persona(gt_userid)
    # Find the query from the experiments list
    exp = next(
        e for e in task["experiments"] if e["gt_userid"] == gt_userid
    )
    user_message = _build_user_message(task, exp, persona)

    model_config = {
        "research_model": MODEL_NAME,
        "compression_model": MODEL_NAME,
        "final_report_model": MODEL_NAME,
        "summarization_model": MODEL_NAME,
        "service_tier": "flex" if use_flex else "default",
        "timeout_sec": TIMEOUT_SEC,
        "max_retries": MAX_RETRIES,
        "requests_per_minute": REQUESTS_PER_MINUTE,
        "retry_initial_delay_sec": RETRY_INITIAL_DELAY_SEC,
    }
    execution_config = {
        "manifest_sha256": manifest_sha256,
        "manifest_version": manifest.get("version"),
        "taskid": task["taskid"],
        "split": task["split"],
        "source_query_id": source_query_id,
        "gt_userid": gt_userid,
        "generation_seed": seed,
        "service_tier": model_config["service_tier"],
        "timeout_sec": TIMEOUT_SEC,
        "max_retries": MAX_RETRIES,
        "models": model_config,
        "search": {
            "provider": "serper_via_tavily_slot",
            "report_query_cap": 7,
            "unique_url_cap": 15,
            "global_hard_stop": 2400,
        },
        "prompt_sha256": _text_sha256(user_message),
    }
    configurable = {
        "allow_clarification": False,
        "search_api": "tavily",
        "max_concurrent_research_units": 3,
        "max_researcher_iterations": 3,
        "max_react_tool_calls": 5,
        "research_model": MODEL_NAME,
        "compression_model": MODEL_NAME,
        "final_report_model": MODEL_NAME,
        "summarization_model": MODEL_NAME,
        "research_model_max_tokens": 8192,
        "compression_model_max_tokens": 8192,
        "final_report_model_max_tokens": 8192,
        "summarization_model_max_tokens": 4096,
    }
    config = {"configurable": configurable, "recursion_limit": 100}

    plan_stub = {
        "models": model_config,
        "search": execution_config["search"],
    }
    raw_dir = output_dir / "serper_raw"
    adapter = SerperAdapter(run_id, ledger, raw_dir, max_queries_per_call=2)
    tracer = DRATracer(
        run_id,
        output_dir,
        search_adapter=adapter,
        execution_config=execution_config,
    )
    handle = patch_search(adapter)
    try:
        with _frozen_runtime_environment(plan_stub):
            async with asyncio.timeout(TIMEOUT_SEC):
                bundle = await tracer.run(
                    deep_researcher,
                    [HumanMessage(content=user_message)],
                    config,
                )
    finally:
        restore_search(handle)

    validation = validate_artifact_file(tracer.output_path)
    summary = {
        "run_id": run_id,
        "taskid": task["taskid"],
        "domain": task["domain"],
        "gt_userid": gt_userid,
        "seed": seed,
        "artifact_path": str(tracer.output_path),
        "schema_valid": validation["schema_valid"],
        "success_criteria_met": validation["success_criteria_met"],
        "completeness_errors": validation["completeness_errors"],
        "schema_errors": validation["schema_errors"],
        "ledger_errors": validation["ledger_errors"],
        "token_ledger": bundle.token_ledger,
        "execution_error": bundle.execution_error,
    }
    summary_path = output_dir / f"{run_id}_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False, sort_keys=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--split",
        choices=["dev", "confirmatory"],
        default="dev",
        help="Manifest split to run",
    )
    parser.add_argument("--seed", type=int, default=0, help="Generation seed")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "runs" / "pilot",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Call external APIs (requires DRA_ALLOW_EXTERNAL_API=1)",
    )
    parser.add_argument(
        "--no-flex",
        action="store_true",
        help="Use default pay-as-you-go tier instead of Flex",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip runs whose artifact already exists and is schema_valid",
    )
    args = parser.parse_args(argv)
    use_flex = not args.no_flex

    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)

    import hashlib
    manifest_sha256 = hashlib.sha256(
        args.manifest.read_bytes()
    ).hexdigest()

    experiments = _iter_experiments(manifest, args.split, args.seed)

    print(f"split={args.split}  seed={args.seed}  model={MODEL_NAME}")
    print(f"flex={'yes' if use_flex else 'no'}  experiments={len(experiments)}")
    print(f"output={args.output_dir}")
    print()

    if args.execute:
        if os.environ.get(ALLOW_ENV, "").strip() != "1":
            print(f"ERROR: set {ALLOW_ENV}=1 to allow external API calls", file=sys.stderr)
            return 1
        for key in ("SERPER_API_KEY",):
            if not os.environ.get(key, "").strip():
                print(f"ERROR: {key} is required for --execute", file=sys.stderr)
                return 1
        if not (
            os.environ.get("GOOGLE_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
        ):
            print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY required", file=sys.stderr)
            return 1

        from scripts.dry_run import (
            _ensure_import_path,
            _install_configurable_model,
            _verify_model_wiring,
        )
        from scripts.serper_adapter import GlobalLedger
        from scripts.tracing_adapter import validate_artifact_file

        _ensure_import_path()
        model_api_key = (
            os.environ.get("GOOGLE_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
        )
        _install_configurable_model(
            model_name=MODEL_NAME,
            seed=args.seed,
            timeout_sec=TIMEOUT_SEC,
            max_retries=MAX_RETRIES,
            requests_per_minute=REQUESTS_PER_MINUTE,
            retry_initial_delay_sec=RETRY_INITIAL_DELAY_SEC,
            use_flex=use_flex,
        )
        _verify_model_wiring(
            model_name=MODEL_NAME,
            api_key=model_api_key,
            seed=args.seed,
            timeout_sec=TIMEOUT_SEC,
            requests_per_minute=REQUESTS_PER_MINUTE,
            retry_initial_delay_sec=RETRY_INITIAL_DELAY_SEC,
            use_flex=use_flex,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        ledger = GlobalLedger(args.output_dir / "global_query_ledger.json")

        results = []
        for idx, (task, gt_userid, seed, source_query_id) in enumerate(experiments, 1):
            rid = _run_id(task["taskid"], gt_userid, seed)
            artifact_path = args.output_dir / f"{rid}_artifacts.json"
            label = f"[{idx}/{len(experiments)}] {rid}"

            if args.resume and artifact_path.exists():
                try:
                    v = validate_artifact_file(artifact_path)
                    if v["schema_valid"]:
                        print(f"{label}  SKIP (schema_valid artifact exists)")
                        results.append({"run_id": rid, "skipped": True})
                        continue
                except Exception:
                    pass

            print(f"{label}  task={task['taskid']} {task['domain']}  gt={gt_userid}")
            try:
                summary = asyncio.run(
                    _run_one(
                        manifest=manifest,
                        manifest_path=args.manifest,
                        manifest_sha256=manifest_sha256,
                        task=task,
                        gt_userid=gt_userid,
                        seed=seed,
                        source_query_id=source_query_id,
                        run_id=rid,
                        output_dir=args.output_dir,
                        ledger=ledger,
                        use_flex=use_flex,
                    )
                )
                status = "OK" if summary["schema_valid"] else "SCHEMA_FAIL"
                if summary["completeness_errors"]:
                    status += f" completeness_errors={summary['completeness_errors']}"
                print(f"  {status}  tokens={summary['token_ledger'].get('total_tokens')}  elapsed={summary['token_ledger'].get('elapsed_sec')}s")
                results.append(summary)
            except Exception as exc:
                print(f"  ERROR: {exc}", file=sys.stderr)
                results.append({"run_id": rid, "error": str(exc)})

        batch_summary_path = args.output_dir / f"batch_{args.split}_seed{args.seed}_summary.json"
        with open(batch_summary_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False, sort_keys=True)
        print(f"\nBatch summary → {batch_summary_path}")

        ok = sum(1 for r in results if r.get("schema_valid"))
        skip = sum(1 for r in results if r.get("skipped"))
        fail = len(results) - ok - skip
        print(f"schema_valid={ok}  skipped={skip}  failed={fail}")
        return 0 if fail == 0 else 1

    else:
        # Plan-only: just print what would run
        for idx, (task, gt_userid, seed, source_query_id) in enumerate(experiments, 1):
            rid = _run_id(task["taskid"], gt_userid, seed)
            print(
                f"[{idx}/{len(experiments)}] {rid}  "
                f"task={task['taskid']} {task['domain']}  "
                f"query_id={source_query_id}"
            )
        print(
            f"\nPlan only. Re-run with --execute and {ALLOW_ENV}=1 to start."
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
