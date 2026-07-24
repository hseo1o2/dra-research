"""Artifact and ledger tracing for the DRA open_deep_research pipeline.

The tracer consumes LangChain/LangGraph v2 events because nested researcher
graphs are invoked inside ``supervisor_tools``. Update-stream namespaces alone
cannot distinguish concurrent researcher invocations; event parent run IDs can.

Captured artifacts:
  1. research brief and ordered research topics
  2. search queries and normalized selected sources
  3. compressed research keyed by deterministic topic ID
  4. final report
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


ARTIFACT_SCHEMA_VERSION = "dra_trace_v1"
SEARCH_TOOL_NAMES = {"serper_search", "tavily_search"}
ERROR_REPORT_PREFIXES = (
    "Error generating final report:",
    "Error synthesizing research report:",
)
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _atomic_json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                data,
                handle,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _iter_messages(value: Any, seen: set[int] | None = None) -> Iterator[BaseMessage]:
    """Yield messages from common LangChain event output containers."""
    if seen is None:
        seen = set()
    if value is None:
        return
    value_id = id(value)
    if value_id in seen:
        return
    seen.add(value_id)

    if isinstance(value, BaseMessage):
        yield value
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_messages(item, seen)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_messages(item, seen)
        return
    for attribute in ("message", "generations", "update"):
        child = getattr(value, attribute, None)
        if child is not None:
            yield from _iter_messages(child, seen)


def _find_field(value: Any, key: str, seen: set[int] | None = None) -> Any:
    """Find a named value in dicts or LangGraph ``Command.update`` payloads."""
    if seen is None:
        seen = set()
    if value is None:
        return None
    value_id = id(value)
    if value_id in seen:
        return None
    seen.add(value_id)
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for item in value.values():
            found = _find_field(item, key, seen)
            if found is not None:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            found = _find_field(item, key, seen)
            if found is not None:
                return found
        return None
    update = getattr(value, "update", None)
    if update is not None:
        return _find_field(update, key, seen)
    return None


def _message_content(value: Any) -> str:
    if isinstance(value, ToolMessage):
        value = value.content
    if isinstance(value, list):
        return "".join(
            str(item.get("text", ""))
            if isinstance(item, dict)
            else str(item)
            for item in value
        )
    return str(value)


@dataclass
class ArtifactBundle:
    """Canonical per-report artifact container."""

    run_id: str
    research_brief: str | None = None
    research_topics: list[dict[str, Any]] = field(default_factory=list)
    search_trace: list[dict[str, Any]] = field(default_factory=list)
    compressed_research: list[dict[str, Any]] = field(default_factory=list)
    final_report: str | None = None
    token_ledger: dict[str, Any] = field(default_factory=dict)
    capture_completeness: dict[str, Any] = field(default_factory=dict)
    execution_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "run_id": self.run_id,
            # Schema requires strings; empty means "not captured" and is
            # reported under completeness_errors rather than schema_errors.
            "research_brief": self.research_brief or "",
            "research_topics": sorted(
                self.research_topics,
                key=lambda item: item["topic_id"],
            ),
            "search_trace": sorted(
                self.search_trace,
                key=lambda item: (item["topic_id"], item["query_id"]),
            ),
            "compressed_research": sorted(
                self.compressed_research,
                key=lambda item: item["topic_id"],
            ),
            "final_report": self.final_report or "",
            "token_ledger": self.token_ledger,
            "capture_completeness": self.capture_completeness,
            "execution_error": self.execution_error,
        }

    def validate(self) -> list[str]:
        report = validate_artifact_data(self.to_dict())
        return (
            report["schema_errors"]
            + report["completeness_errors"]
            + report["ledger_errors"]
        )


class DRATracer:
    """Run a compiled graph and persist deterministic DRA artifacts."""

    def __init__(
        self,
        run_id: str,
        output_dir: Path,
        *,
        search_adapter: Any | None = None,
    ):
        if not _RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError(
                "run_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}"
            )
        self.run_id = run_id
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.search_adapter = search_adapter
        self._bundle = ArtifactBundle(run_id=run_id)

        self._topic_counter = 0
        self._unassigned_topic_ids_by_text: dict[str, deque[str]] = defaultdict(deque)
        self._assigned_topic_ids: set[str] = set()
        self._topic_by_researcher_run: dict[str, str] = {}
        self._topic_by_scope_run: dict[str, str] = {}
        self._compressed_by_topic: dict[str, dict[str, Any]] = {}
        self._query_counter_by_topic: dict[str, int] = defaultdict(int)
        self._query_ids_by_tool_run: dict[str, list[str]] = {}
        self._query_by_id: dict[str, dict[str, Any]] = {}
        self._seen_model_runs: set[str] = set()
        self._run_started = False

    @property
    def output_path(self) -> Path:
        return self.output_dir / f"{self.run_id}_artifacts.json"

    async def run(
        self,
        graph: Any,
        input_messages: list[Any],
        config: dict[str, Any],
    ) -> ArtifactBundle:
        """Run a graph through the nested-event tracer."""
        if self._run_started:
            raise RuntimeError("A DRATracer instance can only run once")
        self._run_started = True
        started = time.monotonic()
        try:
            async for event in graph.astream_events(
                {"messages": input_messages},
                config,
                version="v2",
            ):
                self.process_event(event)
        except BaseException as exc:
            self._bundle.execution_error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            elapsed = round(time.monotonic() - started, 3)
            if self.search_adapter is not None:
                self.search_adapter.finalize()
            self._finalize_bundle(elapsed)
            self._save()
        return self._bundle

    def process_event(self, event: dict[str, Any]) -> None:
        """Consume one LangChain v2 event; public for offline contract tests."""
        event_type = str(event.get("event", ""))
        name = str(event.get("name", ""))
        run_id = str(event.get("run_id", ""))
        data = event.get("data") or {}
        metadata = event.get("metadata") or {}
        node_name = str(metadata.get("langgraph_node") or name)

        if event_type == "on_chat_model_end":
            self._capture_token_usage(run_id, data.get("output"))
            if node_name == "supervisor":
                self._capture_supervisor_topics(data.get("output"))
            return

        if event_type == "on_chain_start" and node_name == "researcher":
            topic_text = _find_field(data.get("input"), "research_topic")
            if isinstance(topic_text, str) and topic_text.strip():
                topic_id = self._assign_topic(topic_text.strip())
                self._topic_by_researcher_run[run_id] = topic_id
                parent_ids = event.get("parent_ids") or []
                if parent_ids:
                    # The final parent is the unique researcher-subgraph run.
                    # Sibling researcher_tools/compress nodes share this scope.
                    self._topic_by_scope_run[str(parent_ids[-1])] = topic_id
            return

        if event_type == "on_tool_start" and name in SEARCH_TOOL_NAMES:
            self._start_search_tool(event)
            return
        if event_type == "on_tool_end" and name in SEARCH_TOOL_NAMES:
            self._finish_search_tool(event)
            return
        if event_type == "on_tool_error" and name in SEARCH_TOOL_NAMES:
            self._fail_search_tool(event)
            return

        if event_type != "on_chain_end":
            return
        output = data.get("output")

        if node_name == "write_research_brief":
            brief = _find_field(output, "research_brief")
            if isinstance(brief, str) and brief.strip():
                self._bundle.research_brief = brief.strip()

        if node_name == "supervisor":
            self._capture_supervisor_topics(output)

        if node_name == "compress_research":
            compressed = _find_field(output, "compressed_research")
            topic_id = self._topic_id_for_event(event)
            topic_text = _find_field(data.get("input"), "research_topic")
            if (
                topic_id is not None
                and isinstance(compressed, str)
                and compressed.strip()
                and not compressed.startswith(ERROR_REPORT_PREFIXES)
            ):
                self._compressed_by_topic[topic_id] = {
                    "topic_id": topic_id,
                    "topic_text": (
                        topic_text.strip()
                        if isinstance(topic_text, str)
                        else self._topic_text(topic_id)
                    ),
                    "compressed_research": compressed.strip(),
                }

        if node_name == "final_report_generation":
            final_report = _find_field(output, "final_report")
            if isinstance(final_report, str) and final_report.strip():
                self._bundle.final_report = final_report.strip()

    def _capture_supervisor_topics(self, value: Any) -> None:
        for message in _iter_messages(value):
            if not isinstance(message, AIMessage):
                continue
            for call in message.tool_calls or []:
                if call.get("name") != "ConductResearch":
                    continue
                topic_text = str(
                    (call.get("args") or {}).get("research_topic", "")
                ).strip()
                if not topic_text:
                    continue
                tool_call_id = str(call.get("id", ""))
                if tool_call_id and any(
                    item.get("_tool_call_id") == tool_call_id
                    for item in self._bundle.research_topics
                ):
                    continue
                self._register_topic(topic_text, tool_call_id)

    def _register_topic(self, topic_text: str, tool_call_id: str = "") -> str:
        self._topic_counter += 1
        topic_id = f"topic_{self._topic_counter:03d}"
        # The tool-call ID is internal only; it is removed before serialization.
        self._bundle.research_topics.append(
            {
                "topic_id": topic_id,
                "topic_text": topic_text,
                "_tool_call_id": tool_call_id,
            }
        )
        self._unassigned_topic_ids_by_text[topic_text].append(topic_id)
        return topic_id

    def _assign_topic(self, topic_text: str) -> str:
        candidates = self._unassigned_topic_ids_by_text[topic_text]
        while candidates and candidates[0] in self._assigned_topic_ids:
            candidates.popleft()
        if candidates:
            topic_id = candidates.popleft()
        else:
            topic_id = self._register_topic(topic_text)
            self._unassigned_topic_ids_by_text[topic_text].pop()
        self._assigned_topic_ids.add(topic_id)
        return topic_id

    def _topic_id_for_event(self, event: dict[str, Any]) -> str | None:
        for parent_id in reversed(event.get("parent_ids") or []):
            parent_id = str(parent_id)
            topic_id = (
                self._topic_by_researcher_run.get(parent_id)
                or self._topic_by_scope_run.get(parent_id)
            )
            if topic_id is not None:
                return topic_id
        run_id = str(event.get("run_id", ""))
        return self._topic_by_researcher_run.get(run_id)

    def _topic_text(self, topic_id: str) -> str:
        for item in self._bundle.research_topics:
            if item["topic_id"] == topic_id:
                return str(item["topic_text"])
        return ""

    def _start_search_tool(self, event: dict[str, Any]) -> None:
        run_id = str(event.get("run_id", ""))
        topic_id = self._topic_id_for_event(event)
        if topic_id is None:
            topic_id = "topic_unmapped"
        inputs = (event.get("data") or {}).get("input") or {}
        queries = inputs.get("queries", []) if isinstance(inputs, dict) else []
        if isinstance(queries, str):
            queries = [queries]
        if not isinstance(queries, list):
            queries = [str(queries)]

        query_ids: list[str] = []
        for raw_query in queries:
            self._query_counter_by_topic[topic_id] += 1
            sequence = self._query_counter_by_topic[topic_id]
            query_id = f"{topic_id}_query_{sequence:03d}"
            query_ids.append(query_id)
            entry = {
                "topic_id": topic_id,
                "query_id": query_id,
                "query": str(raw_query),
                "attempted": None,
                "status": "pending",
                "failure_code": None,
                "sources": [],
            }
            self._query_by_id[query_id] = entry
        self._query_ids_by_tool_run[run_id] = query_ids

    def _finish_search_tool(self, event: dict[str, Any]) -> None:
        run_id = str(event.get("run_id", ""))
        query_ids = self._query_ids_by_tool_run.get(run_id, [])
        expected_queries = [
            str(self._query_by_id[query_id]["query"]) for query_id in query_ids
        ]
        records: list[Any] = []

        # Prefer adapter claim-by-query: model-facing tool text is free-form, and
        # concurrent researchers may finish out of order.
        if self.search_adapter is not None and hasattr(
            self.search_adapter, "claim_records_for_queries"
        ):
            claimed = self.search_adapter.claim_records_for_queries(
                expected_queries
            )
            if isinstance(claimed, list):
                records = claimed

        if not records or all(item is None for item in records):
            output = (event.get("data") or {}).get("output")
            content = _message_content(output)
            try:
                payload = json.loads(content)
            except (TypeError, json.JSONDecodeError):
                if not records:
                    self._apply_legacy_search_output(query_ids, content)
                    return
            else:
                parsed = (
                    payload.get("queries", [])
                    if isinstance(payload, dict)
                    else []
                )
                if isinstance(parsed, list) and parsed:
                    records = parsed

        for index, query_id in enumerate(query_ids):
            entry = self._query_by_id[query_id]
            record = records[index] if index < len(records) else None
            if not isinstance(record, dict):
                entry.update(
                    {
                        "attempted": True,
                        "status": "failure",
                        "failure_code": "trace_missing_query_result",
                    }
                )
                continue
            sources = record.get("sources", [])
            status = str(record.get("status", "failure"))
            if status not in {"ok", "failure"}:
                status = "failure"
            entry.update(
                {
                    "query": str(record.get("query", entry["query"])),
                    "attempted": bool(record.get("attempted", False)),
                    "status": status,
                    "failure_code": record.get("failure_code"),
                    "sources": self._normalize_trace_sources(
                        str(record.get("query", entry["query"])),
                        sources,
                    ),
                }
            )

    def _fail_search_tool(self, event: dict[str, Any]) -> None:
        run_id = str(event.get("run_id", ""))
        error = (event.get("data") or {}).get("error")
        for query_id in self._query_ids_by_tool_run.get(run_id, []):
            self._query_by_id[query_id].update(
                {
                    "attempted": True,
                    "status": "failure",
                    "failure_code": "tool_execution_error",
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    @staticmethod
    def _normalize_trace_sources(
        query: str,
        sources: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(sources, list):
            return []
        normalized: list[dict[str, Any]] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            normalized.append(
                {
                    "query": str(source.get("query", query)),
                    "title": str(source.get("title", "")),
                    "link": str(source.get("link", "")),
                    "domain": str(source.get("domain", "")),
                    "rank": source.get("rank"),
                    "snippet": str(source.get("snippet", "")),
                }
            )
        return normalized

    def _apply_legacy_search_output(
        self,
        query_ids: list[str],
        content: str,
    ) -> None:
        """Mark non-JSON upstream output explicitly; do not invent metadata."""
        for query_id in query_ids:
            self._query_by_id[query_id].update(
                {
                    "attempted": True,
                    "status": "failure",
                    "failure_code": "unstructured_search_output",
                    "raw_output": content,
                }
            )

    def _capture_token_usage(self, run_id: str, output: Any) -> None:
        if not run_id or run_id in self._seen_model_runs:
            return
        input_tokens = 0
        output_tokens = 0
        found = False
        for message in _iter_messages(output):
            usage = getattr(message, "usage_metadata", None) or {}
            response_metadata = getattr(message, "response_metadata", None) or {}
            if not usage:
                usage = (
                    response_metadata.get("usage")
                    or response_metadata.get("token_usage")
                    or response_metadata.get("usage_metadata")
                    or {}
                )
            if not isinstance(usage, dict) or not usage:
                continue
            found = True
            input_tokens += int(
                usage.get("input_tokens")
                or usage.get("prompt_tokens")
                or 0
            )
            output_tokens += int(
                usage.get("output_tokens")
                or usage.get("completion_tokens")
                or 0
            )
        if not found:
            return
        self._seen_model_runs.add(run_id)
        ledger = self._bundle.token_ledger
        ledger["input_tokens"] = ledger.get("input_tokens", 0) + input_tokens
        ledger["output_tokens"] = ledger.get("output_tokens", 0) + output_tokens
        ledger["token_usage_events"] = ledger.get("token_usage_events", 0) + 1

    def _finalize_bundle(self, elapsed: float) -> None:
        # Remove internal, provider-generated identifiers before serialization.
        self._bundle.research_topics = [
            {
                "topic_id": item["topic_id"],
                "topic_text": item["topic_text"],
            }
            for item in self._bundle.research_topics
        ]
        self._bundle.compressed_research = list(
            self._compressed_by_topic.values()
        )

        # Any tool_start without a matching terminal tool_end is an explicit miss.
        for entry in self._query_by_id.values():
            if entry.get("status") == "pending":
                entry.update(
                    {
                        "attempted": True,
                        "status": "failure",
                        "failure_code": "trace_incomplete_tool_call",
                    }
                )

        self._bundle.search_trace = list(self._query_by_id.values())

        ledger = self._bundle.token_ledger
        ledger.setdefault("input_tokens", 0)
        ledger.setdefault("output_tokens", 0)
        ledger.setdefault("token_usage_events", 0)
        ledger["total_tokens"] = (
            ledger["input_tokens"] + ledger["output_tokens"]
        )
        ledger["queries_requested"] = len(self._bundle.search_trace)
        ledger["queries_attempted"] = sum(
            item["attempted"] is True
            for item in self._bundle.search_trace
        )
        ledger["queries_successful"] = sum(
            item["status"] == "ok"
            for item in self._bundle.search_trace
        )
        ledger["queries_failed"] = sum(
            item["attempted"] is True and item["status"] != "ok"
            for item in self._bundle.search_trace
        )
        ledger["queries_rejected"] = sum(
            item["attempted"] is False
            for item in self._bundle.search_trace
        )
        ledger["sources_selected"] = sum(
            len(item["sources"])
            for item in self._bundle.search_trace
        )
        unique_links = {
            source["link"]
            for item in self._bundle.search_trace
            for source in item["sources"]
            if source["link"]
        }
        ledger["unique_sources"] = len(unique_links)
        ledger["elapsed_sec"] = elapsed

        if self.search_adapter is not None:
            adapter_ledger = self.search_adapter.ledger_snapshot()
            ledger["search_adapter"] = adapter_ledger
            ledger["query_ledger_consistent"] = (
                ledger["queries_requested"]
                == adapter_ledger["run_queries_requested"]
                and ledger["queries_attempted"]
                == adapter_ledger["run_queries_attempted"]
                and ledger["queries_successful"]
                == adapter_ledger["run_queries_successful"]
                and ledger["queries_failed"]
                == adapter_ledger["run_queries_failed"]
            )
            ledger["source_ledger_consistent"] = (
                ledger["sources_selected"]
                == adapter_ledger["run_sources_selected"]
                and ledger["unique_sources"]
                == adapter_ledger["run_unique_urls"]
            )
        else:
            ledger["query_ledger_consistent"] = True
            ledger["source_ledger_consistent"] = True

        topic_ids = {
            item["topic_id"] for item in self._bundle.research_topics
        }
        compressed_ids = {
            item["topic_id"] for item in self._bundle.compressed_research
        }
        search_terminal = bool(self._bundle.search_trace) and all(
            item["status"] in {"ok", "failure"}
            for item in self._bundle.search_trace
        )
        successful_queries_have_sources = any(
            item["status"] == "ok" and item["sources"]
            for item in self._bundle.search_trace
        )
        self._bundle.capture_completeness = {
            "research_brief": bool(self._bundle.research_brief),
            "research_topics_ordered": bool(topic_ids),
            "search_query_and_source": (
                search_terminal and successful_queries_have_sources
            ),
            "compressed_research_per_topic": (
                bool(topic_ids) and compressed_ids == topic_ids
            ),
            "final_report": bool(self._bundle.final_report)
            and not self._bundle.final_report.startswith(
                ERROR_REPORT_PREFIXES
            ),
            "four_required_artifacts": False,
        }
        required = self._bundle.capture_completeness
        required["four_required_artifacts"] = all(
            (
                required["research_brief"],
                required["research_topics_ordered"],
                required["search_query_and_source"],
                required["compressed_research_per_topic"],
                required["final_report"],
            )
        )

    def _save(self) -> None:
        _atomic_json_write(self.output_path, self._bundle.to_dict())


REQUIRED_KEYS = {
    "schema_version",
    "run_id",
    "research_brief",
    "research_topics",
    "search_trace",
    "compressed_research",
    "final_report",
    "token_ledger",
    "capture_completeness",
}


def validate_artifact_data(data: Any) -> dict[str, list[str]]:
    """Validate schema, artifact completeness, and ledger reconciliation."""
    schema_errors: list[str] = []
    completeness_errors: list[str] = []
    ledger_errors: list[str] = []

    if not isinstance(data, dict):
        return {
            "schema_errors": ["root must be an object"],
            "completeness_errors": [],
            "ledger_errors": [],
        }
    missing = sorted(REQUIRED_KEYS - set(data))
    schema_errors.extend(f"missing key: {key}" for key in missing)
    if missing:
        return {
            "schema_errors": schema_errors,
            "completeness_errors": completeness_errors,
            "ledger_errors": ledger_errors,
        }
    if data["schema_version"] != ARTIFACT_SCHEMA_VERSION:
        schema_errors.append("unsupported schema_version")
    if not isinstance(data["run_id"], str) or not data["run_id"]:
        schema_errors.append("run_id must be a non-empty string")
    if not isinstance(data["research_brief"], str):
        schema_errors.append("research_brief must be a string")
    for key in ("research_topics", "search_trace", "compressed_research"):
        if not isinstance(data[key], list):
            schema_errors.append(f"{key} must be a list")
    if not isinstance(data["final_report"], str):
        schema_errors.append("final_report must be a string")
    if not isinstance(data["token_ledger"], dict):
        schema_errors.append("token_ledger must be an object")
    if schema_errors:
        return {
            "schema_errors": schema_errors,
            "completeness_errors": completeness_errors,
            "ledger_errors": ledger_errors,
        }

    topics = data["research_topics"]
    expected_topic_ids = [
        f"topic_{index:03d}" for index in range(1, len(topics) + 1)
    ]
    actual_topic_ids: list[str] = []
    for index, topic in enumerate(topics):
        if not isinstance(topic, dict):
            schema_errors.append(f"research_topics[{index}] must be an object")
            continue
        if set(topic) != {"topic_id", "topic_text"}:
            schema_errors.append(
                f"research_topics[{index}] has invalid keys"
            )
        topic_id = topic.get("topic_id")
        topic_text = topic.get("topic_text")
        if not isinstance(topic_id, str):
            schema_errors.append(
                f"research_topics[{index}].topic_id must be a string"
            )
        else:
            actual_topic_ids.append(topic_id)
        if not isinstance(topic_text, str) or not topic_text:
            schema_errors.append(
                f"research_topics[{index}].topic_text must be non-empty"
            )
    if actual_topic_ids != expected_topic_ids:
        schema_errors.append("topic IDs must be ordered and contiguous")

    query_ids: set[str] = set()
    for index, query in enumerate(data["search_trace"]):
        if not isinstance(query, dict):
            schema_errors.append(f"search_trace[{index}] must be an object")
            continue
        required_query_keys = {
            "topic_id",
            "query_id",
            "query",
            "attempted",
            "status",
            "failure_code",
            "sources",
        }
        if not required_query_keys <= set(query):
            schema_errors.append(
                f"search_trace[{index}] missing required fields"
            )
            continue
        query_id = query["query_id"]
        if not isinstance(query_id, str) or query_id in query_ids:
            schema_errors.append(
                f"search_trace[{index}].query_id invalid or duplicate"
            )
        query_ids.add(query_id)
        if (
            query["topic_id"] not in actual_topic_ids
            and query["topic_id"] != "topic_unmapped"
        ):
            schema_errors.append(
                f"search_trace[{index}] references unknown topic"
            )
        if query["topic_id"] == "topic_unmapped":
            completeness_errors.append(
                f"search_trace[{index}] is not mapped to a research topic"
            )
        if not isinstance(query["query"], str) or not query["query"]:
            schema_errors.append(
                f"search_trace[{index}].query must be non-empty"
            )
        if query["attempted"] not in (True, False):
            schema_errors.append(
                f"search_trace[{index}].attempted must be boolean"
            )
        if query["status"] not in {"ok", "failure"}:
            schema_errors.append(
                f"search_trace[{index}].status is not terminal"
            )
        if not isinstance(query["sources"], list):
            schema_errors.append(
                f"search_trace[{index}].sources must be a list"
            )
            continue
        for source_index, source in enumerate(query["sources"]):
            required_source_keys = {
                "query",
                "title",
                "link",
                "domain",
                "rank",
                "snippet",
            }
            if not isinstance(source, dict) or set(source) != required_source_keys:
                schema_errors.append(
                    f"search_trace[{index}].sources[{source_index}] invalid"
                )
                continue
            if not isinstance(source["rank"], int) or source["rank"] < 1:
                schema_errors.append(
                    f"search_trace[{index}].sources[{source_index}].rank invalid"
                )
            for field_name in ("query", "title", "link", "domain", "snippet"):
                if not isinstance(source[field_name], str):
                    schema_errors.append(
                        f"search_trace[{index}].sources[{source_index}]."
                        f"{field_name} must be a string"
                    )

    compressed_ids: list[str] = []
    for index, compressed in enumerate(data["compressed_research"]):
        required_compressed_keys = {
            "topic_id",
            "topic_text",
            "compressed_research",
        }
        if (
            not isinstance(compressed, dict)
            or set(compressed) != required_compressed_keys
        ):
            schema_errors.append(
                f"compressed_research[{index}] has invalid schema"
            )
            continue
        compressed_ids.append(compressed["topic_id"])
        if (
            not isinstance(compressed["compressed_research"], str)
            or not compressed["compressed_research"]
        ):
            schema_errors.append(
                f"compressed_research[{index}] is empty"
            )

    if not data["research_brief"]:
        completeness_errors.append("research_brief not captured")
    if not topics:
        completeness_errors.append("research_topics not captured")
    if not data["search_trace"]:
        completeness_errors.append("search query not captured")
    if not any(
        item.get("status") == "ok" and item.get("sources")
        for item in data["search_trace"]
        if isinstance(item, dict)
    ):
        completeness_errors.append("search source not captured")
    if sorted(compressed_ids) != sorted(actual_topic_ids):
        completeness_errors.append(
            "compressed_research is not one-to-one with topics"
        )
    if not data["final_report"] or data["final_report"].startswith(
        ERROR_REPORT_PREFIXES
    ):
        completeness_errors.append("final_report not captured successfully")

    ledger = data["token_ledger"]
    integer_fields = {
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "token_usage_events",
        "queries_requested",
        "queries_attempted",
        "queries_successful",
        "queries_failed",
        "queries_rejected",
        "sources_selected",
        "unique_sources",
    }
    for key in integer_fields:
        if not isinstance(ledger.get(key), int) or ledger[key] < 0:
            ledger_errors.append(f"invalid ledger field: {key}")
    if not ledger_errors:
        queries = data["search_trace"]
        expected_attempted = sum(
            item["attempted"] is True for item in queries
        )
        expected_success = sum(item["status"] == "ok" for item in queries)
        expected_failed = sum(
            item["attempted"] is True and item["status"] != "ok"
            for item in queries
        )
        expected_rejected = sum(
            item["attempted"] is False for item in queries
        )
        expected_sources = sum(len(item["sources"]) for item in queries)
        expected_unique = len(
            {
                source["link"]
                for item in queries
                for source in item["sources"]
                if source["link"]
            }
        )
        comparisons = {
            "queries_requested": len(queries),
            "queries_attempted": expected_attempted,
            "queries_successful": expected_success,
            "queries_failed": expected_failed,
            "queries_rejected": expected_rejected,
            "sources_selected": expected_sources,
            "unique_sources": expected_unique,
        }
        for key, expected in comparisons.items():
            if ledger[key] != expected:
                ledger_errors.append(
                    f"{key} mismatch: {ledger[key]} != {expected}"
                )
        if ledger["total_tokens"] != (
            ledger["input_tokens"] + ledger["output_tokens"]
        ):
            ledger_errors.append("total_tokens mismatch")
        if ledger["token_usage_events"] == 0:
            ledger_errors.append("no token usage metadata captured")
        if ledger.get("query_ledger_consistent") is not True:
            ledger_errors.append("search adapter query ledger mismatch")
        if ledger.get("source_ledger_consistent") is not True:
            ledger_errors.append("search adapter source ledger mismatch")

    return {
        "schema_errors": schema_errors,
        "completeness_errors": completeness_errors,
        "ledger_errors": ledger_errors,
    }


def validate_artifact_file(path: Path) -> dict[str, Any]:
    """Load an artifact file and report all Day-3 success criteria."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    validation = validate_artifact_data(data)
    schema_valid = not validation["schema_errors"]
    success = not any(validation.values())
    return {
        "path": str(path),
        "schema_valid": schema_valid,
        "success_criteria_met": success,
        **validation,
        "completeness": data.get("capture_completeness", {}),
    }
