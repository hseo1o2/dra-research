"""Day-3 1-query dry-run for DRA Personalization.

Default mode is plan-only (no external API). Live execution requires both:
  1. CLI flag ``--execute``
  2. Environment ``DRA_ALLOW_EXTERNAL_API=1``

Live run uses:
  - manifest.json ``pdr_bench.dev[0]`` (task 3 Education by freeze)
  - first persona in ``personas_n3``
  - generation seed 0
  - Serper adapter (``SERPER_API_KEY``)
  - Gemini models with ``service_tier=flex`` (``GOOGLE_API_KEY`` / ``GEMINI_API_KEY``)

Credentials are read from the environment only and never written to artifacts.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "manifest.json"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass
DEFAULT_OUTPUT = ROOT / "runs" / "dry_run"
PERSONAS_PATH = ROOT / "data" / "pdr-bench" / "persona_data" / "personas_en.jsonl"

# Keep DRA imports local so ``--help`` works without the research venv.
ALLOW_ENV = "DRA_ALLOW_EXTERNAL_API"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_persona(userid: str) -> dict[str, Any]:
    with open(PERSONAS_PATH, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            persona = json.loads(line)
            if persona.get("userid") == userid:
                return persona
    raise KeyError(f"Persona not found: {userid}")


def _select_dev0(manifest: dict[str, Any]) -> dict[str, Any]:
    dev = manifest["pdr_bench"]["dev"]
    if not dev:
        raise ValueError("manifest.pdr_bench.dev is empty")
    return dev[0]


def _persona_prompt_block(persona: dict[str, Any]) -> str:
    """Serialize the full persona JSON for conditioning (no secrets)."""
    payload = {k: v for k, v in persona.items() if k != "userid"}
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _build_user_message(
    task: dict[str, Any],
    experiment: dict[str, Any],
    persona: dict[str, Any],
) -> str:
    """Return one frozen task/persona prompt without double conditioning."""
    query = str(experiment.get("query", "")).strip()
    if not query:
        raise ValueError("experiment.query is empty")
    if "User Persona:" in query:
        return query
    return (
        f"User Task:\n{query or task['task']}\n\n"
        f"User Persona:\n{_persona_prompt_block(persona)}\n"
    )


def _plan(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    task = _select_dev0(manifest)
    experiment = task["experiments"][0]
    userid = experiment["gt_userid"]
    persona = _load_persona(userid)
    seed = manifest.get("generation", {}).get("pilot", {}).get("seeds", [0])[0]
    run_id = (
        f"dryrun_task{task['taskid']}_{userid}_seed{seed}"
    )
    plan = {
        "mode": "plan",
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "manifest_version": manifest.get("version"),
        "manifest_seed": manifest.get("seed"),
        "taskid": task["taskid"],
        "domain": task["domain"],
        "split": task["split"],
        "gt_userid": userid,
        "source_query_id": experiment["source_query_id"],
        "query_preview": experiment["query"][:200],
        "generation_seed": seed,
        "run_id": run_id,
        "output_dir": str(output_dir),
        "artifact_path": str(output_dir / f"{run_id}_artifacts.json"),
        "models": {
            "research_model": "google_genai:gemini-3.6-flash",
            "compression_model": "google_genai:gemini-3.6-flash",
            "final_report_model": "google_genai:gemini-3.6-flash",
            "summarization_model": "google_genai:gemini-3.6-flash",
            "service_tier": "flex",
            "timeout_sec": 900,
            "max_retries": 3,
            "requests_per_minute": 4,
            "retry_initial_delay_sec": 15,
        },
        "search": {
            "provider": "serper_via_tavily_slot",
            "report_query_cap": 7,
            "unique_url_cap": 15,
            "global_hard_stop": 2400,
        },
        "success_criteria": [
            "four required artifacts captured",
            "schema validation pass",
            "topic-id deterministic serialization",
            "query/source/token ledger consistent",
        ],
        "execute_requirements": [
            "pass --execute",
            f"set {ALLOW_ENV}=1",
            "set SERPER_API_KEY",
            "set GOOGLE_API_KEY or GEMINI_API_KEY",
        ],
        "persona_fields_present": sorted(persona.keys()),
    }
    return plan


def _require_live_env() -> None:
    if os.environ.get(ALLOW_ENV, "").strip() != "1":
        raise SystemExit(
            f"Refusing live dry-run: set {ALLOW_ENV}=1 after explicit approval."
        )
    if not os.environ.get("SERPER_API_KEY", "").strip():
        raise SystemExit("SERPER_API_KEY is required for --execute")
    if not (
        os.environ.get("GOOGLE_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    ):
        raise SystemExit(
            "GOOGLE_API_KEY or GEMINI_API_KEY is required for --execute"
        )


@contextmanager
def _frozen_runtime_environment(plan: dict[str, Any]):
    """Prevent ambient ODR settings from overriding the frozen dry-run plan."""
    overrides = {
        "RESEARCH_MODEL": plan["models"]["research_model"],
        "COMPRESSION_MODEL": plan["models"]["compression_model"],
        "FINAL_REPORT_MODEL": plan["models"]["final_report_model"],
        "SUMMARIZATION_MODEL": plan["models"]["summarization_model"],
        "SEARCH_API": "tavily",
    }
    previous = {name: os.environ.get(name) for name in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _ensure_import_path() -> None:
    root = str(ROOT)
    odr_src = str(ROOT / "open_deep_research" / "src")
    for path in (root, odr_src):
        if path not in sys.path:
            sys.path.insert(0, path)


def _install_configurable_model(
    *,
    model_name: str,
    seed: int,
    timeout_sec: int,
    max_retries: int,
    requests_per_minute: int,
    retry_initial_delay_sec: int,
    use_flex: bool,
) -> None:
    """Rebind all graph model calls with seed, timeout, retries, and optional Flex.

    When ``use_flex=True``, patches the LangChain request builder to inject
    ``service_tier=flex`` on every outgoing Gemini request.  When False, the
    default pay-as-you-go tier is used (higher priority, no extra patch needed).
    """
    import open_deep_research.deep_researcher as odr_module
    from langchain.chat_models import init_chat_model
    from langchain_core.rate_limiters import InMemoryRateLimiter
    from langchain_google_genai import ChatGoogleGenerativeAI
    from google.genai.types import HttpOptions, HttpRetryOptions

    already_patched = getattr(
        ChatGoogleGenerativeAI._build_request_config,
        "_dra_flex_patch",
        False,
    )
    if use_flex and not already_patched:
        original_builder = ChatGoogleGenerativeAI._build_request_config

        def build_request_config_flex(self, *args, **kwargs):
            request = original_builder(self, *args, **kwargs)
            http_options = request.http_options or HttpOptions()
            http_options.retry_options = HttpRetryOptions(
                attempts=max_retries,
                initial_delay=retry_initial_delay_sec,
                max_delay=60,
                exp_base=2,
                jitter=1,
                http_status_codes=[408, 429, 500, 502, 503, 504],
            )
            extra_body = dict(http_options.extra_body or {})
            configured_tier = extra_body.get("service_tier")
            if configured_tier not in (None, "flex"):
                raise ValueError(
                    f"Refusing non-Flex service tier: {configured_tier}"
                )
            extra_body["service_tier"] = "flex"
            http_options.extra_body = extra_body
            request.http_options = http_options
            return request

        build_request_config_flex._dra_flex_patch = True
        ChatGoogleGenerativeAI._build_request_config = (
            build_request_config_flex
        )

    rate_limiter = InMemoryRateLimiter(
        requests_per_second=requests_per_minute / 60,
        check_every_n_seconds=0.2,
        max_bucket_size=1,
    )
    odr_module.configurable_model = init_chat_model(
        model=model_name,
        seed=seed,
        timeout=timeout_sec,
        max_retries=max_retries,
        rate_limiter=rate_limiter,
        configurable_fields=("model", "max_tokens", "api_key"),
    )


# Keep old name as alias so existing callers and tests are unaffected.
_install_flex_configurable_model = _install_configurable_model


def _verify_model_wiring(
    *,
    model_name: str,
    api_key: str,
    seed: int,
    timeout_sec: int,
    requests_per_minute: int,
    retry_initial_delay_sec: int,
    use_flex: bool,
) -> None:
    """Resolve one model locally and prove the outgoing request configuration."""
    import open_deep_research.deep_researcher as odr_module
    from langchain_core.messages import HumanMessage

    model = odr_module.configurable_model._model(
        {
            "model": model_name,
            "api_key": api_key,
            "max_tokens": 16,
        }
    )
    request = model._prepare_request([HumanMessage(content="wiring check")])
    http_options = request["config"].http_options
    retry_options = http_options.retry_options if http_options else None
    limiter = model.rate_limiter
    actual_tier = (http_options.extra_body or {}).get("service_tier") if http_options else None
    flex_ok = actual_tier == "flex" if use_flex else actual_tier in (None, "auto", "default")
    if (
        model.seed != seed
        or model.timeout != timeout_sec
        or model.client.vertexai
        or limiter is None
        or limiter.requests_per_second != requests_per_minute / 60
        or limiter.max_bucket_size != 1
        or not flex_ok
        or (use_flex and (retry_options is None
            or retry_options.attempts != model.max_retries
            or retry_options.initial_delay != retry_initial_delay_sec
            or 429 not in (retry_options.http_status_codes or [])))
    ):
        raise RuntimeError(
            "Gemini Developer API/rate-limit wiring verification failed"
        )


async def _run_live(plan: dict[str, Any], manifest_path: Path, *, use_flex: bool) -> dict[str, Any]:
    _require_live_env()
    _ensure_import_path()

    from langchain_core.messages import HumanMessage

    from open_deep_research.deep_researcher import deep_researcher
    from scripts.serper_adapter import (
        GlobalLedger,
        SerperAdapter,
        patch_search,
        restore_search,
    )
    from scripts.tracing_adapter import DRATracer, validate_artifact_file

    manifest = _load_manifest(manifest_path)
    task = _select_dev0(manifest)
    experiment = task["experiments"][0]
    persona = _load_persona(experiment["gt_userid"])
    seed = int(plan["generation_seed"])
    timeout_sec = int(plan["models"]["timeout_sec"])
    max_retries = int(plan["models"]["max_retries"])
    requests_per_minute = int(plan["models"]["requests_per_minute"])
    retry_initial_delay_sec = int(
        plan["models"]["retry_initial_delay_sec"]
    )
    model_api_key = (
        os.environ.get("GOOGLE_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )
    _install_configurable_model(
        model_name=plan["models"]["research_model"],
        seed=seed,
        timeout_sec=timeout_sec,
        max_retries=max_retries,
        requests_per_minute=requests_per_minute,
        retry_initial_delay_sec=retry_initial_delay_sec,
        use_flex=use_flex,
    )
    _verify_model_wiring(
        model_name=plan["models"]["research_model"],
        api_key=model_api_key,
        seed=seed,
        timeout_sec=timeout_sec,
        requests_per_minute=requests_per_minute,
        retry_initial_delay_sec=retry_initial_delay_sec,
        use_flex=use_flex,
    )
    run_id = plan["run_id"]
    output_dir = Path(plan["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    ledger = GlobalLedger(output_dir / "global_query_ledger.json")
    raw_dir = output_dir / "serper_raw"
    model_name = plan["models"]["research_model"]
    configurable = {
        "allow_clarification": False,
        "search_api": "tavily",  # routed to Serper by patch_search
        "max_concurrent_research_units": 3,
        "max_researcher_iterations": 3,
        "max_react_tool_calls": 5,
        "research_model": model_name,
        "compression_model": plan["models"]["compression_model"],
        "final_report_model": plan["models"]["final_report_model"],
        "summarization_model": plan["models"]["summarization_model"],
        "research_model_max_tokens": 8192,
        "compression_model_max_tokens": 8192,
        "final_report_model_max_tokens": 8192,
        "summarization_model_max_tokens": 4096,
    }
    config = {
        "configurable": configurable,
        "recursion_limit": 100,
    }

    user_message = _build_user_message(task, experiment, persona)
    adapter = SerperAdapter(run_id, ledger, raw_dir, max_queries_per_call=2)
    tracer = DRATracer(
        run_id,
        output_dir,
        search_adapter=adapter,
        execution_config={
            "manifest_sha256": plan["manifest_sha256"],
            "manifest_version": plan["manifest_version"],
            "taskid": plan["taskid"],
            "split": plan["split"],
            "source_query_id": plan["source_query_id"],
            "gt_userid": plan["gt_userid"],
            "generation_seed": seed,
            "service_tier": "flex" if use_flex else "default",
            "timeout_sec": timeout_sec,
            "max_retries": max_retries,
            "models": dict(plan["models"]),
            "search": dict(plan["search"]),
            "prompt_sha256": _text_sha256(user_message),
        },
    )
    handle = patch_search(adapter)
    try:
        with _frozen_runtime_environment(plan):
            async with asyncio.timeout(timeout_sec):
                bundle = await tracer.run(
                    deep_researcher,
                    [HumanMessage(content=user_message)],
                    config,
                )
    finally:
        restore_search(handle)

    validation = validate_artifact_file(tracer.output_path)
    summary = {
        "mode": "execute",
        "run_id": run_id,
        "artifact_path": str(tracer.output_path),
        "capture_completeness": bundle.capture_completeness,
        "token_ledger": bundle.token_ledger,
        "validation": {
            "schema_valid": validation["schema_valid"],
            "success_criteria_met": validation["success_criteria_met"],
            "schema_errors": validation["schema_errors"],
            "completeness_errors": validation["completeness_errors"],
            "ledger_errors": validation["ledger_errors"],
        },
        "execution_error": bundle.execution_error,
    }
    summary_path = output_dir / f"{run_id}_dry_run_summary.json"
    with open(summary_path, "w", encoding="utf-8") as handle_out:
        json.dump(summary, handle_out, indent=2, ensure_ascii=False, sort_keys=True)
    summary["summary_path"] = str(summary_path)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to frozen manifest.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory for artifacts and ledgers",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually call Gemini/Serper (requires DRA_ALLOW_EXTERNAL_API=1)",
    )
    parser.add_argument(
        "--no-flex",
        action="store_true",
        help="Use default pay-as-you-go tier instead of Flex (for dry-run / off-peak override)",
    )
    args = parser.parse_args(argv)
    use_flex = not args.no_flex

    plan = _plan(args.manifest, args.output_dir)
    if not args.execute:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        print(
            "\nPlan only. No external API was called. "
            f"Re-run with --execute and {ALLOW_ENV}=1 after approval.",
            file=sys.stderr,
        )
        return 0

    try:
        summary = asyncio.run(_run_live(plan, args.manifest, use_flex=use_flex))
    except BaseException as exc:
        # Never dump env or secrets; surface type + message only.
        print(f"dry-run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not summary["validation"]["success_criteria_met"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
