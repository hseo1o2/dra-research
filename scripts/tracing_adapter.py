"""
Tracing adapter for open_deep_research DRA pipeline.

Wraps the compiled deep_researcher graph and captures 4 mandatory artifacts
per run via LangGraph's subgraph-aware streaming API:

  1. research_brief + ordered research_topics   (Planning stage)
  2. search query + source trace                (Search-Research stage)
  3. compressed_research per topic              (Compression stage)
  4. final_report                               (Writing stage)

Also records a per-run token/query ledger.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage


# ── Artifact container ────────────────────────────────────────────────────────

@dataclass
class ArtifactBundle:
    run_id: str
    # Stage 1: Planning
    research_brief: str | None = None
    research_topics: list[str] = field(default_factory=list)
    # Stage 2: Search-Research — list of {query, sources: [{title,domain,rank,snippet,url}]}
    search_trace: list[dict] = field(default_factory=list)
    # Stage 3: Compression — list of {topic_id, topic_text, compressed_research}
    compressed_research: list[dict] = field(default_factory=list)
    # Stage 4: Writing
    final_report: str | None = None
    # Ledger
    token_ledger: dict = field(default_factory=dict)
    capture_completeness: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return list of missing required fields."""
        missing = []
        if not self.research_brief:
            missing.append("research_brief")
        if not self.research_topics:
            missing.append("research_topics")
        if not self.compressed_research:
            missing.append("compressed_research")
        if not self.final_report:
            missing.append("final_report")
        return missing

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "research_brief": self.research_brief,
            "research_topics": self.research_topics,
            "search_trace": self.search_trace,
            "compressed_research": self.compressed_research,
            "final_report": self.final_report,
            "token_ledger": self.token_ledger,
            "capture_completeness": self.capture_completeness,
        }


# ── Tracer ────────────────────────────────────────────────────────────────────

class DRATracer:
    """
    Run a compiled deep_researcher graph and capture artifacts.

    Usage:
        tracer = DRATracer(run_id="pdr_t2_u2_s0", output_dir=Path("artifacts/runs"))
        bundle = await tracer.run(graph, input_messages, config)
        assert not bundle.validate(), bundle.validate()
    """

    def __init__(self, run_id: str, output_dir: Path):
        self.run_id = run_id
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._bundle = ArtifactBundle(run_id=run_id)
        # track researcher topic assignments: namespace_key -> topic_text
        self._topic_by_ns: dict[str, str] = {}
        self._topic_counter: int = 0

    async def run(
        self,
        graph,
        input_messages: list,
        config: dict,
    ) -> ArtifactBundle:
        """Run the graph and return the populated ArtifactBundle."""
        t0 = time.monotonic()

        async for namespace, event in graph.astream(
            {"messages": input_messages},
            config,
            stream_mode="updates",
            subgraphs=True,
        ):
            for node_name, update in event.items():
                self._process_event(namespace, node_name, update)

        elapsed = round(time.monotonic() - t0, 2)
        self._bundle.capture_completeness = {
            "research_brief": self._bundle.research_brief is not None,
            "research_topics_count": len(self._bundle.research_topics),
            "search_queries_count": len(self._bundle.search_trace),
            "compressed_research_count": len(self._bundle.compressed_research),
            "final_report": self._bundle.final_report is not None,
            "elapsed_sec": elapsed,
        }
        self._bundle.token_ledger["elapsed_sec"] = elapsed
        self._save()
        return self._bundle

    # ── Event routing ─────────────────────────────────────────────────────────

    def _process_event(self, namespace: tuple, node_name: str, update: Any) -> None:
        if not isinstance(update, dict):
            return

        # ── Stage 1: Planning ─────────────────────────────────────────────────
        if node_name == "write_research_brief":
            rb = update.get("research_brief")
            if rb:
                self._bundle.research_brief = rb

        # ── Supervisor tool calls: extract ConductResearch topics ─────────────
        if node_name == "supervisor":
            for msg in update.get("supervisor_messages", []):
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc.get("name") == "ConductResearch":
                            topic_text = tc["args"].get("research_topic", "")
                            if topic_text and topic_text not in self._bundle.research_topics:
                                self._bundle.research_topics.append(topic_text)

        # ── Stage 2: Search — AIMessage tool calls inside researcher ─────────
        if node_name == "researcher":
            ns_key = self._ns_key(namespace)
            for msg in update.get("researcher_messages", []):
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc.get("name") in ("serper_search", "tavily_search"):
                            queries = tc["args"].get("queries", [])
                            for q in queries:
                                self._bundle.search_trace.append({
                                    "ns_key": ns_key,
                                    "query": q,
                                    "sources": [],  # filled from ToolMessage below
                                    "tool_call_id": tc.get("id"),
                                })
                    # record which topic this researcher handles
                    rt = update.get("research_topic") or ""
                    if rt and ns_key not in self._topic_by_ns:
                        self._topic_by_ns[ns_key] = rt

        # ── Stage 2: Search — ToolMessage results ────────────────────────────
        if node_name == "researcher_tools":
            ns_key = self._ns_key(namespace)
            for msg in update.get("researcher_messages", []):
                from langchain_core.messages import ToolMessage
                if isinstance(msg, ToolMessage) and msg.name in (
                    "serper_search", "tavily_search"
                ):
                    # attach snippet sources back to the matching search_trace entry
                    self._attach_sources(ns_key, msg)

        # ── Stage 3: Compression ─────────────────────────────────────────────
        if node_name == "compress_research":
            ns_key = self._ns_key(namespace)
            cr = update.get("compressed_research")
            if cr and cr != "Error synthesizing research report: Maximum retries exceeded":
                self._topic_counter += 1
                self._bundle.compressed_research.append({
                    "topic_id": self._topic_counter,
                    "ns_key": ns_key,
                    "topic_text": self._topic_by_ns.get(ns_key, ""),
                    "compressed_research": cr,
                })

        # ── Stage 4: Final report ─────────────────────────────────────────────
        if node_name == "final_report_generation":
            fr = update.get("final_report")
            if fr:
                self._bundle.final_report = fr

        # ── Token ledger (best-effort from response_metadata) ─────────────────
        self._accum_tokens(update)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ns_key(self, namespace: tuple) -> str:
        return ":".join(str(x) for x in namespace) if namespace else "root"

    def _attach_sources(self, ns_key: str, tool_msg) -> None:
        """Parse source lines from the formatted search output and attach."""
        content = str(tool_msg.content)
        sources: list[dict] = []
        for line in content.splitlines():
            if line.startswith("URL: "):
                sources.append({"url": line[5:].strip()})
            elif line.startswith("--- SOURCE "):
                # title embedded in "--- SOURCE N: Title ---"
                inner = line.lstrip("- ").rstrip("- ")
                parts = inner.split(": ", 1)
                if len(parts) == 2 and sources and "title" not in sources[-1]:
                    sources[-1]["title"] = parts[1]
        # attach to the latest matching search entry for this ns_key
        for entry in reversed(self._bundle.search_trace):
            if entry["ns_key"] == ns_key and not entry["sources"]:
                entry["sources"] = sources
                break

    def _accum_tokens(self, update: dict) -> None:
        """Accumulate token counts from message metadata (best-effort)."""
        ledger = self._bundle.token_ledger
        for msgs in update.values():
            if not isinstance(msgs, list):
                continue
            for msg in msgs:
                meta = getattr(msg, "response_metadata", {}) or {}
                usage = meta.get("usage") or meta.get("token_usage") or {}
                if not usage:
                    continue
                ledger["input_tokens"] = ledger.get("input_tokens", 0) + (
                    usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                )
                ledger["output_tokens"] = ledger.get("output_tokens", 0) + (
                    usage.get("output_tokens") or usage.get("completion_tokens") or 0
                )

    def _save(self) -> None:
        out = self.output_dir / f"{self.run_id}_artifacts.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(self._bundle.to_dict(), f, indent=2, ensure_ascii=False)


# ── Schema validation helper ──────────────────────────────────────────────────

REQUIRED_KEYS = {
    "run_id", "research_brief", "research_topics",
    "compressed_research", "final_report",
}

def validate_artifact_file(path: Path) -> dict:
    """Load an artifact JSON and return a validation report."""
    with open(path) as f:
        data = json.load(f)
    missing = REQUIRED_KEYS - set(data.keys())
    null_fields = [k for k in REQUIRED_KEYS if data.get(k) in (None, [], "")]
    return {
        "path": str(path),
        "schema_valid": len(missing) == 0,
        "missing_keys": list(missing),
        "null_or_empty_fields": null_fields,
        "completeness": data.get("capture_completeness", {}),
    }
