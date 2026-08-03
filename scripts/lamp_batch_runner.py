"""LaMP-QA replication runner for the frozen DRA-PULSE manifest.

The default is a network-free plan of all 90 runs (15 questions × 3 candidate
profiles × 2 seeds). Live execution additionally requires ``--execute``, one
specific seed, ``--acknowledge-pdr-finished``, and ``DRA_ALLOW_EXTERNAL_API=1``.

Examples:
    python scripts/lamp_batch_runner.py
    python scripts/lamp_batch_runner.py --seed 0

    # Only after PDR generation has stopped:
    DRA_ALLOW_EXTERNAL_API=1 python scripts/lamp_batch_runner.py \
      --seed 0 --execute --acknowledge-pdr-finished
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ODR_SRC = str(ROOT / "open_deep_research" / "src")
if ODR_SRC not in sys.path:
    sys.path.insert(0, ODR_SRC)

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from scripts.batch_runner import (  # noqa: E402
    ALLOW_ENV,
    MAX_RETRIES,
    MODEL_NAME,
    REQUESTS_PER_MINUTE,
    RETRY_INITIAL_DELAY_SEC,
    TIMEOUT_SEC,
    _repository_state,
)
from scripts.dry_run import _frozen_runtime_environment, _text_sha256  # noqa: E402


DEFAULT_MANIFEST = ROOT / "manifest.json"
DEFAULT_DATA_ROOT = ROOT / "data" / "lamp-qa" / "data"
DEFAULT_OUTPUT = ROOT / "runs" / "lamp_qa"
DEFAULT_PLAN_OUT = ROOT / "provenance" / "lamp_qa_run_plan.json"
DEFAULT_GLOBAL_LEDGER = ROOT / "runs" / "confirmatory" / "global_query_ledger.json"
SEEDS = (0, 1)
CATEGORY_SLUGS = {
    "Art_and_Entertainment": "art",
    "Lifestyle_and_Personal_Development": "lifestyle",
    "Society_and_Culture": "society",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _profile_text(profile: list[dict[str, Any]]) -> str:
    """Serialize historical LaMP-QA items without rubric/answer leakage."""
    cleaned = [
        {
            "id": str(item.get("id", "")),
            "category": str(item.get("category", "")),
            "text": str(item.get("text", "")),
        }
        for item in profile
    ]
    return json.dumps(cleaned, ensure_ascii=False, indent=2, sort_keys=True)


def build_user_message(question: str, profile: list[dict[str, Any]]) -> str:
    question = question.strip()
    if not question:
        raise ValueError("LaMP-QA question is empty")
    if not profile:
        raise ValueError("LaMP-QA profile is empty")
    return (
        f"User Task:\n{question}\n\n"
        "User Persona (historical question context):\n"
        f"{_profile_text(profile)}\n"
    )


def _category_items(
    category: str,
    data_root: Path,
) -> tuple[dict[str, dict[str, Any]], Path, str]:
    path = data_root / category / "train" / "train.json"
    with path.open(encoding="utf-8") as handle:
        items = json.load(handle)
    by_id = {str(item["id"]): item for item in items}
    if len(by_id) != len(items):
        raise ValueError(f"Duplicate LaMP-QA item IDs in {path}")
    return by_id, path, _sha256(path)


def iter_experiments(
    manifest: dict[str, Any],
    data_root: Path,
    seeds: tuple[int, ...] = SEEDS,
) -> list[dict[str, Any]]:
    queries = manifest.get("lamp_qa", {}).get("queries", [])
    if len(queries) != 15:
        raise ValueError(f"Expected 15 frozen LaMP-QA queries, found {len(queries)}")

    cache: dict[str, tuple[dict[str, dict[str, Any]], Path, str]] = {}
    rows: list[dict[str, Any]] = []
    for query_index, query in enumerate(queries, 1):
        category = query["category"]
        if category not in CATEGORY_SLUGS:
            raise ValueError(f"Unexpected LaMP-QA category: {category}")
        if category not in cache:
            cache[category] = _category_items(category, data_root)
        by_id, source_path, source_sha256 = cache[category]
        candidate_ids = query["attribution_candidate_set_n3"]
        if len(candidate_ids) != 3 or len(set(candidate_ids)) != 3:
            raise ValueError(f"Query {query_index} does not have 3 unique candidates")

        gt_item_id = str(query["item_id"])
        if candidate_ids[0] != gt_item_id:
            raise ValueError(f"Query {query_index} must list GT candidate first")
        if gt_item_id not in by_id:
            raise KeyError(f"Missing GT item {gt_item_id} in {source_path}")
        if by_id[gt_item_id]["question"] != query["question"]:
            raise ValueError(f"Question mismatch for {gt_item_id}")
        if len(by_id[gt_item_id].get("profile", [])) != query["gt_profile_len"]:
            raise ValueError(f"GT profile length mismatch for {gt_item_id}")

        for candidate_position, candidate_id in enumerate(candidate_ids):
            candidate_id = str(candidate_id)
            if candidate_id not in by_id:
                raise KeyError(f"Missing candidate {candidate_id} in {source_path}")
            profile = by_id[candidate_id].get("profile", [])
            if not profile:
                raise ValueError(f"Empty profile for candidate {candidate_id}")
            serialized_profile = _profile_text(profile)
            prompt = build_user_message(query["question"], profile)
            profile_sha256 = _text_sha256(serialized_profile)
            prompt_sha256 = _text_sha256(prompt)
            for seed in seeds:
                run_id = (
                    f"lamp_{CATEGORY_SLUGS[category]}_q{query_index:02d}_"
                    f"{candidate_id}_seed{seed}"
                )
                rows.append(
                    {
                        "run_id": run_id,
                        "query_index": query_index,
                        "category": category,
                        "question_item_id": gt_item_id,
                        "candidate_profile_item_id": candidate_id,
                        "candidate_position": candidate_position,
                        "is_gt_profile": candidate_id == gt_item_id,
                        "generation_seed": seed,
                        "profile_items": profile,
                        "profile_items_count": len(profile),
                        "profile_sha256": profile_sha256,
                        "prompt": prompt,
                        "prompt_sha256": prompt_sha256,
                        "source_path": source_path,
                        "source_sha256": source_sha256,
                    }
                )
    return rows


def plan_payload(
    manifest_path: Path,
    data_root: Path,
    seeds: tuple[int, ...],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    rows = iter_experiments(manifest, data_root, seeds)
    public_rows = [
        {
            key: row[key]
            for key in (
                "run_id",
                "query_index",
                "category",
                "question_item_id",
                "candidate_profile_item_id",
                "candidate_position",
                "is_gt_profile",
                "generation_seed",
                "profile_items_count",
                "profile_sha256",
                "prompt_sha256",
                "source_sha256",
            )
        }
        for row in rows
    ]
    payload = {
        "schema_version": 1,
        "mode": "plan_only",
        "external_api_calls": 0,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "data_root": str(data_root),
        "seeds": list(seeds),
        "expected_runs": len(rows),
        "design": {
            "queries": len({row["query_index"] for row in rows}),
            "candidate_profiles_per_query": 3,
            "gt_profiles_per_query": 1,
            "hard_negative_profiles_per_query": 2,
        },
        "execution_guard": (
            "Live mode requires one seed, --execute, "
            "--acknowledge-pdr-finished, and DRA_ALLOW_EXTERNAL_API=1."
        ),
        "runs": public_rows,
    }
    return payload, rows


async def _run_one(
    *,
    manifest: dict[str, Any],
    manifest_sha256: str,
    row: dict[str, Any],
    output_dir: Path,
    ledger: Any,
    use_flex: bool,
) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage

    from open_deep_research.deep_researcher import deep_researcher
    from scripts.serper_adapter import SerperAdapter, patch_search, restore_search
    from scripts.tracing_adapter import DRATracer, validate_artifact_file

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
        "dataset": "lamp_qa",
        "split": "replication",
        "query_index": row["query_index"],
        "question_item_id": row["question_item_id"],
        "candidate_profile_item_id": row["candidate_profile_item_id"],
        "candidate_position": row["candidate_position"],
        "is_gt_profile": row["is_gt_profile"],
        "generation_seed": row["generation_seed"],
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
        "prompt_sha256": row["prompt_sha256"],
        "profile_sha256": row["profile_sha256"],
        "source_sha256": row["source_sha256"],
        **_repository_state(),
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
    plan_stub = {"models": model_config, "search": execution_config["search"]}

    adapter = SerperAdapter(
        row["run_id"],
        ledger,
        output_dir / "serper_raw",
        max_queries_per_call=2,
    )
    tracer = DRATracer(
        row["run_id"],
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
                    [HumanMessage(content=row["prompt"])],
                    config,
                )
    finally:
        restore_search(handle)

    validation = validate_artifact_file(tracer.output_path)
    summary = {
        "run_id": row["run_id"],
        "dataset": "lamp_qa",
        "query_index": row["query_index"],
        "category": row["category"],
        "question_item_id": row["question_item_id"],
        "candidate_profile_item_id": row["candidate_profile_item_id"],
        "candidate_position": row["candidate_position"],
        "is_gt_profile": row["is_gt_profile"],
        "seed": row["generation_seed"],
        "artifact_path": str(tracer.output_path),
        "schema_valid": validation["schema_valid"],
        "success_criteria_met": validation["success_criteria_met"],
        "completeness_errors": validation["completeness_errors"],
        "schema_errors": validation["schema_errors"],
        "ledger_errors": validation["ledger_errors"],
        "token_ledger": bundle.token_ledger,
        "execution_error": bundle.execution_error,
    }
    (output_dir / f"{row['run_id']}_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _write_batch_summary(
    output_dir: Path,
    seed: int,
    rows: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> dict[str, Any]:
    current_by_id = {item["run_id"]: item for item in current}
    results: list[dict[str, Any]] = []
    for row in rows:
        summary_path = output_dir / f"{row['run_id']}_summary.json"
        if summary_path.exists():
            try:
                results.append(json.loads(summary_path.read_text(encoding="utf-8")))
                continue
            except (OSError, json.JSONDecodeError):
                pass
        results.append(
            current_by_id.get(row["run_id"], {"run_id": row["run_id"], "missing": True})
        )
    quality = {
        "expected_runs": len(rows),
        "completed_runs": sum(item.get("schema_valid") is not None for item in results),
        "missing_runs": sum(bool(item.get("missing")) for item in results),
        "error_runs": sum(bool(item.get("error")) for item in results),
        "schema_valid_runs": sum(item.get("schema_valid") is True for item in results),
        "success_criteria_met_runs": sum(
            item.get("success_criteria_met") is True for item in results
        ),
    }
    (output_dir / f"batch_lamp_qa_seed{seed}_summary.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / f"batch_lamp_qa_seed{seed}_quality_summary.json").write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return quality


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--seed", choices=["0", "1", "all"], default="all")
    parser.add_argument("--plan-out", type=Path, default=DEFAULT_PLAN_OUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--global-ledger", type=Path, default=DEFAULT_GLOBAL_LEDGER)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--acknowledge-pdr-finished", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-flex", action="store_true")
    args = parser.parse_args(argv)

    seeds = SEEDS if args.seed == "all" else (int(args.seed),)
    plan, rows = plan_payload(args.manifest.resolve(), args.data_root.resolve(), seeds)
    args.plan_out.parent.mkdir(parents=True, exist_ok=True)
    args.plan_out.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"LaMP-QA plan: {plan['expected_runs']} runs "
        f"({plan['design']['queries']} queries × 3 profiles × {len(seeds)} seed(s))"
    )
    print(f"Plan: {args.plan_out}")

    if not args.execute:
        for index, row in enumerate(rows, 1):
            print(
                f"[{index}/{len(rows)}] {row['run_id']}  "
                f"q={row['question_item_id']}  "
                f"profile={row['candidate_profile_item_id']}"
            )
        print("Plan only. External API calls: 0")
        return 0

    if args.seed == "all":
        print("ERROR: live execution requires one explicit seed (0 or 1)", file=sys.stderr)
        return 1
    if not args.acknowledge_pdr_finished:
        print(
            "ERROR: live execution requires --acknowledge-pdr-finished",
            file=sys.stderr,
        )
        return 1
    if os.environ.get(ALLOW_ENV, "").strip() != "1":
        print(f"ERROR: set {ALLOW_ENV}=1 to allow external API calls", file=sys.stderr)
        return 1
    if not os.environ.get("SERPER_API_KEY", "").strip():
        print("ERROR: SERPER_API_KEY is required", file=sys.stderr)
        return 1
    model_api_key = (
        os.environ.get("GOOGLE_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )
    if not model_api_key:
        print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY is required", file=sys.stderr)
        return 1

    from scripts.dry_run import (
        _ensure_import_path,
        _install_configurable_model,
        _verify_model_wiring,
    )
    from scripts.serper_adapter import GlobalLedger
    from scripts.tracing_adapter import validate_artifact_file

    _ensure_import_path()
    use_flex = not args.no_flex
    seed = seeds[0]
    _install_configurable_model(
        model_name=MODEL_NAME,
        seed=seed,
        timeout_sec=TIMEOUT_SEC,
        max_retries=MAX_RETRIES,
        requests_per_minute=REQUESTS_PER_MINUTE,
        retry_initial_delay_sec=RETRY_INITIAL_DELAY_SEC,
        use_flex=use_flex,
    )
    _verify_model_wiring(
        model_name=MODEL_NAME,
        api_key=model_api_key,
        seed=seed,
        timeout_sec=TIMEOUT_SEC,
        requests_per_minute=REQUESTS_PER_MINUTE,
        retry_initial_delay_sec=RETRY_INITIAL_DELAY_SEC,
        use_flex=use_flex,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = GlobalLedger(args.global_ledger)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest_sha256 = _sha256(args.manifest)

    results: list[dict[str, Any]] = []
    executed = 0
    for index, row in enumerate(rows, 1):
        if args.limit is not None and executed >= args.limit:
            break
        artifact_path = args.output_dir / f"{row['run_id']}_artifacts.json"
        if args.resume and artifact_path.exists():
            validation = validate_artifact_file(artifact_path)
            if validation["schema_valid"]:
                print(f"[{index}/{len(rows)}] {row['run_id']} SKIP")
                continue
        print(f"[{index}/{len(rows)}] {row['run_id']}")
        try:
            results.append(
                asyncio.run(
                    _run_one(
                        manifest=manifest,
                        manifest_sha256=manifest_sha256,
                        row=row,
                        output_dir=args.output_dir,
                        ledger=ledger,
                        use_flex=use_flex,
                    )
                )
            )
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            results.append({"run_id": row["run_id"], "error": str(exc)})
        executed += 1

    quality = _write_batch_summary(args.output_dir, seed, rows, results)
    print(
        f"completed={quality['completed_runs']}/{quality['expected_runs']} "
        f"schema_valid={quality['schema_valid_runs']} "
        f"errors={quality['error_runs']}"
    )
    return 0 if quality["error_runs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
