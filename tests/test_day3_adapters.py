"""Network-free contract tests for the Day-3 adapters."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from langchain_core.messages import AIMessage

from scripts.serper_adapter import (
    FailureCode,
    GlobalLedger,
    SerperAdapter,
    make_serper_tool,
    patch_search,
    restore_search,
)
from scripts.tracing_adapter import (
    DRATracer,
    validate_artifact_data,
    validate_artifact_file,
)


class MockSerperAdapter(SerperAdapter):
    """Return deterministic organic results without opening a socket."""

    async def _call_serper(self, query, api_key, session):
        if query == "empty":
            return {"organic": []}
        return {
            "organic": [
                {
                    "title": f"{query} title {rank}",
                    "link": f"https://example{rank}.com/{query}#fragment",
                    "position": rank,
                    "snippet": f"{query} snippet {rank}",
                }
                for rank in range(1, 4)
            ]
        }


class FakeEventGraph:
    def __init__(self, events):
        self.events = events

    async def astream_events(self, inputs, config, version):
        assert version == "v2"
        for event in self.events:
            yield event


def event(kind, name, run_id, data, *, parents=(), node=None):
    return {
        "event": kind,
        "name": name,
        "run_id": run_id,
        "parent_ids": list(parents),
        "data": data,
        "metadata": {"langgraph_node": node or name},
    }


def test_missing_api_key_is_explicit_failure(tmp_path, monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    ledger = GlobalLedger(tmp_path / "global.json")
    adapter = MockSerperAdapter("missing-key", ledger, tmp_path / "raw")

    payload = json.loads(asyncio.run(adapter.search(["query"])))

    assert payload["status"] == "failure"
    assert payload["queries"][0]["failure_code"] == FailureCode.MISSING_API_KEY
    assert payload["queries"][0]["attempted"] is False
    assert adapter.ledger_snapshot()["run_queries_attempted"] == 0


def test_report_caps_normalization_and_idempotent_finalize(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("SERPER_API_KEY", "test-only-not-real")
    ledger = GlobalLedger(tmp_path / "global.json")
    adapter = MockSerperAdapter("cap-run", ledger, tmp_path / "raw")

    payload = json.loads(
        asyncio.run(adapter.search([f"q{index}" for index in range(1, 9)]))
    )
    queries = payload["queries"]

    assert [item["query_sequence"] for item in queries] == list(range(1, 9))
    assert sum(item["attempted"] for item in queries) == 7
    assert queries[-1]["failure_code"] == FailureCode.REPORT_QUERY_CAP_EXCEEDED
    assert adapter.ledger_snapshot()["run_unique_urls"] == 15
    assert adapter.ledger_snapshot()["run_queries_successful"] == 5
    assert adapter.ledger_snapshot()["run_queries_failed"] == 2
    assert adapter.ledger_snapshot()["global_attempted_queries"] == 7
    first_source = queries[0]["sources"][0]
    assert set(first_source) == {
        "query",
        "title",
        "link",
        "domain",
        "rank",
        "snippet",
    }
    assert first_source["link"].endswith("/q1")

    adapter.finalize()
    adapter.finalize()
    global_data = json.loads((tmp_path / "global.json").read_text())
    assert global_data["attempted_queries"] == 7
    assert global_data["successful_queries"] == 5
    assert len(global_data["runs"]) == 1


def test_max_queries_per_call_limits_each_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-only-not-real")
    ledger = GlobalLedger(tmp_path / "global.json")
    adapter = MockSerperAdapter(
        "percall-run", ledger, tmp_path / "raw", max_queries_per_call=2
    )

    # First call: 5 queries sent, only 2 should be attempted
    payload1 = json.loads(asyncio.run(adapter.search([f"q{i}" for i in range(1, 6)])))
    assert sum(q["attempted"] for q in payload1["queries"]) == 2
    assert all(
        q["failure_code"] == FailureCode.REPORT_QUERY_CAP_EXCEEDED
        for q in payload1["queries"]
        if not q["attempted"]
    )

    # Second call: 5 more queries, another 2 attempted
    payload2 = json.loads(asyncio.run(adapter.search([f"q{i}" for i in range(6, 11)])))
    assert sum(q["attempted"] for q in payload2["queries"]) == 2

    # Third call: 2 attempted, cap now at 6/7
    payload3 = json.loads(asyncio.run(adapter.search([f"q{i}" for i in range(11, 14)])))
    assert sum(q["attempted"] for q in payload3["queries"]) == 2

    # Fourth call: only 1 slot remains even though max_queries_per_call=2
    payload4 = json.loads(asyncio.run(adapter.search(["q14", "q15"])))
    assert sum(q["attempted"] for q in payload4["queries"]) == 1

    assert adapter.ledger_snapshot()["run_queries_attempted"] == 7


def test_empty_organic_has_failure_code(tmp_path, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-only-not-real")
    ledger = GlobalLedger(tmp_path / "global.json")
    adapter = MockSerperAdapter("empty-run", ledger, tmp_path / "raw")

    payload = json.loads(asyncio.run(adapter.search(["empty"])))

    assert payload["queries"][0]["failure_code"] == FailureCode.EMPTY_ORGANIC
    assert payload["queries"][0]["attempted"] is True
    assert ledger.attempted_queries == 1
    assert ledger.successful_queries == 0


def test_global_reservation_prevents_hard_stop_overshoot(tmp_path):
    ledger_path = tmp_path / "global.json"
    ledger_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "successful_queries": 2399,
                "reservations": {},
                "runs": [],
            }
        )
    )
    ledger = GlobalLedger(ledger_path)

    reservation, granted = ledger.reserve("run-a", 2)
    blocked_reservation, blocked_grant = ledger.reserve("run-b", 1)
    assert granted == 1
    assert blocked_reservation is None
    assert blocked_grant == 0

    ledger.settle(reservation, attempted=1, successful=1)
    assert ledger.attempted_queries == 2400
    assert ledger.successful_queries == 2400


def test_search_patch_is_context_local(tmp_path, monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    ledger = GlobalLedger(tmp_path / "global.json")
    adapter_a = MockSerperAdapter("context-a", ledger, tmp_path / "raw-a")
    adapter_b = MockSerperAdapter("context-b", ledger, tmp_path / "raw-b")

    async def worker(adapter, query):
        import open_deep_research.utils as odr_utils
        from open_deep_research.configuration import SearchAPI

        handle = patch_search(adapter)
        try:
            await asyncio.sleep(0)
            search_tool = (await odr_utils.get_search_tool(SearchAPI.TAVILY))[0]
            await search_tool.ainvoke({"queries": [query]})
        finally:
            restore_search(handle)

    async def run_workers():
        await asyncio.gather(
            worker(adapter_a, "query-a"),
            worker(adapter_b, "query-b"),
        )

    asyncio.run(run_workers())

    assert adapter_a._search_log[0]["query"] == "query-a"
    assert adapter_b._search_log[0]["query"] == "query-b"


def test_model_facing_tool_format_is_tavily_like(tmp_path, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-only-not-real")
    ledger = GlobalLedger(tmp_path / "global.json")
    adapter = MockSerperAdapter("format-run", ledger, tmp_path / "raw")
    tool = make_serper_tool(adapter)

    text = asyncio.run(tool.ainvoke({"queries": ["alpha"]}))

    assert "Search results:" in text
    assert "SOURCE 1:" in text
    assert "URL: https://example1.com/alpha" in text
    assert "SUMMARY:" in text
    # Structured records must remain claimable for the tracer.
    claimed = adapter.claim_records_for_queries(["alpha"])
    assert claimed[0] is not None
    assert claimed[0]["query"] == "alpha"
    assert claimed[0]["status"] == "ok"


def test_tracer_orders_topics_and_reconciles_ledgers(tmp_path, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-only-not-real")
    ledger = GlobalLedger(tmp_path / "global.json")
    adapter = MockSerperAdapter("trace-run", ledger, tmp_path / "raw")
    # Structured search still populates the FIFO batch used by the tracer.
    asyncio.run(adapter.search(["alpha"]))
    asyncio.run(adapter.search(["beta"]))

    supervisor = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "ConductResearch",
                "args": {"research_topic": "Topic A"},
                "id": "call-a",
                "type": "tool_call",
            },
            {
                "name": "ConductResearch",
                "args": {"research_topic": "Topic B"},
                "id": "call-b",
                "type": "tool_call",
            },
        ],
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        },
    )
    researcher_usage = AIMessage(
        content="research",
        usage_metadata={
            "input_tokens": 20,
            "output_tokens": 4,
            "total_tokens": 24,
        },
    )
    writer_usage = AIMessage(
        content="report",
        usage_metadata={
            "input_tokens": 30,
            "output_tokens": 6,
            "total_tokens": 36,
        },
    )
    duplicate_supervisor_wrapper = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "ConductResearch",
                "args": {"research_topic": "Topic B"},
                "id": "call-b-wrapper",
                "type": "tool_call",
            }
        ],
    )

    # Each researcher node and its sibling tool/compression nodes share a unique
    # subgraph scope. Topic B finishes first to exercise canonical serialization.
    events = [
        event(
            "on_chain_end",
            "write_research_brief",
            "brief",
            {"output": {"research_brief": "Brief"}},
        ),
        event(
            "on_chat_model_end",
            "model",
            "model-supervisor",
            {"output": supervisor},
            node="supervisor",
        ),
        event(
            "on_chat_model_end",
            "model-wrapper",
            "model-supervisor-wrapper",
            {"output": duplicate_supervisor_wrapper},
            node="supervisor",
        ),
        event(
            "on_chain_start",
            "researcher",
            "researcher-a",
            {"input": {"research_topic": "Topic A"}},
            parents=["shared", "scope-a"],
        ),
        event(
            "on_chain_start",
            "researcher",
            "researcher-b",
            {"input": {"research_topic": "Topic B"}},
            parents=["shared", "scope-b"],
        ),
        event(
            "on_tool_start",
            "serper_search",
            "tool-b",
            {"input": {"queries": ["beta"]}},
            parents=["shared", "scope-b", "researcher-tools-b"],
        ),
        event(
            "on_tool_end",
            "serper_search",
            "tool-b",
            # Model-facing text is intentionally non-JSON; tracer uses adapter batch.
            {"output": "Search results: beta"},
            parents=["shared", "scope-b", "researcher-tools-b"],
        ),
        event(
            "on_chain_end",
            "research-subgraph-wrapper",
            "compress-b",
            {
                "input": {"research_topic": "Topic B"},
                "output": {"compressed_research": "Compressed B"},
            },
            parents=["shared", "scope-b"],
            node="research_subgraph",
        ),
        event(
            "on_tool_start",
            "serper_search",
            "tool-a",
            {"input": {"queries": ["alpha"]}},
            parents=["shared", "scope-a", "researcher-tools-a"],
        ),
        event(
            "on_tool_end",
            "serper_search",
            "tool-a",
            {"output": "Search results: alpha"},
            parents=["shared", "scope-a", "researcher-tools-a"],
        ),
        event(
            "on_chain_end",
            "compress_research",
            "compress-a",
            {
                "input": {"research_topic": "Topic A"},
                "output": {"compressed_research": "Compressed A"},
            },
            parents=["shared", "scope-a"],
        ),
        event(
            "on_chat_model_end",
            "model",
            "model-researcher",
            {"output": researcher_usage},
            node="researcher",
        ),
        event(
            "on_chat_model_end",
            "model",
            "model-writer",
            {"output": writer_usage},
            node="final_report_generation",
        ),
        event(
            "on_chain_end",
            "final_report_generation",
            "final",
            {"output": {"final_report": "Final report"}},
        ),
    ]

    tracer = DRATracer(
        "trace-run",
        tmp_path / "artifacts",
        search_adapter=adapter,
        execution_config={
            "generation_seed": 0,
            "manifest_sha256": "a" * 64,
            "models": {"research_model": "mock"},
            "prompt_sha256": "b" * 64,
            "service_tier": "flex",
            "timeout_sec": 900,
        },
    )
    asyncio.run(tracer.run(FakeEventGraph(events), [], {}))
    artifact = json.loads(tracer.output_path.read_text())
    validation = validate_artifact_file(tracer.output_path)

    assert validation["success_criteria_met"], validation
    assert len(artifact["research_topics"]) == 2
    assert [
        item["topic_id"] for item in artifact["compressed_research"]
    ] == ["topic_001", "topic_002"]
    assert [
        item["query"] for item in artifact["search_trace"]
    ] == ["alpha", "beta"]
    assert artifact["token_ledger"]["total_tokens"] == 75
    assert artifact["token_ledger"]["query_ledger_consistent"] is True
    assert artifact["token_ledger"]["source_ledger_consistent"] is True
    assert artifact["execution_config"]["service_tier"] == "flex"
    assert artifact["execution_config"]["generation_seed"] == 0

    missing_topic_source = json.loads(json.dumps(artifact))
    beta = next(
        item
        for item in missing_topic_source["search_trace"]
        if item["topic_id"] == "topic_002"
    )
    beta.update(
        {
            "status": "failure",
            "failure_code": "test_failure",
            "sources": [],
        }
    )
    incomplete = validate_artifact_data(missing_topic_source)
    assert any(
        "topic_002" in error
        for error in incomplete["completeness_errors"]
    )


def test_dry_run_plan_only_uses_manifest_dev0(tmp_path, monkeypatch):
    from scripts.dry_run import (
        _build_user_message,
        _frozen_runtime_environment,
        _load_persona,
        _plan,
    )

    manifest_path = Path(__file__).resolve().parents[1] / "manifest.json"
    plan = _plan(manifest_path, tmp_path)
    assert plan["taskid"] == 3
    assert plan["domain"] == "Education"
    assert plan["generation_seed"] == 0
    assert plan["gt_userid"]
    assert plan["run_id"].startswith("dryrun_task3_")
    manifest = json.loads(Path(plan["manifest_path"]).read_text())
    task = manifest["pdr_bench"]["dev"][0]
    experiment = task["experiments"][0]
    persona = _load_persona(experiment["gt_userid"])
    message = _build_user_message(task, experiment, persona)
    assert message == experiment["query"].strip()
    assert message.count("User Persona:") == 1

    import os

    monkeypatch.setenv("RESEARCH_MODEL", "gemini/gemini-2.5-flash")
    monkeypatch.setenv("SEARCH_API", "none")
    with _frozen_runtime_environment(plan):
        assert os.environ["RESEARCH_MODEL"] == "google_genai:gemini-3.6-flash"
        assert os.environ["SEARCH_API"] == "tavily"
    assert os.environ["RESEARCH_MODEL"] == "gemini/gemini-2.5-flash"
    assert os.environ["SEARCH_API"] == "none"


def test_model_wiring_includes_flex_seed_and_timeout(monkeypatch):
    from scripts.dry_run import (
        _ensure_import_path,
        _install_flex_configurable_model,
        _verify_model_wiring,
    )

    monkeypatch.setenv("GOOGLE_API_KEY", "test-only-not-real")
    _ensure_import_path()
    _install_flex_configurable_model(
        model_name="google_genai:gemini-3.6-flash",
        seed=7,
        timeout_sec=900,
        max_retries=3,
        requests_per_minute=4,
        retry_initial_delay_sec=15,
    )
    _verify_model_wiring(
        model_name="google_genai:gemini-3.6-flash",
        api_key="test-only-not-real",
        seed=7,
        timeout_sec=900,
        requests_per_minute=4,
        retry_initial_delay_sec=15,
    )
