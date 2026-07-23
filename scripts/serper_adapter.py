"""
Serper custom search adapter for open_deep_research.

Monkey-patches open_deep_research.utils.get_search_tool so that
SearchAPI.TAVILY routes to Serper instead, keeping upstream code untouched.

Caps (per Notion §5.2):
  - 7 queries max per report
  - 3 organic results max per query
  - 15 unique URLs max per report
  - 2400 successful queries global hard stop
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

import aiohttp
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool

QUERIES_PER_REPORT_MAX = 7
RESULTS_PER_QUERY_MAX = 3
UNIQUE_URLS_PER_REPORT_MAX = 15
GLOBAL_QUERY_HARD_STOP = 2400
SEARCH_TIMEOUT_SEC = 120

_SERPER_URL = "https://google.serper.dev/search"

SERPER_SEARCH_DESCRIPTION = (
    "A search engine for comprehensive, accurate web results. "
    "Useful for answering questions about current events and research topics."
)


class QueryCapExceeded(Exception):
    pass


# ── Global ledger (persisted to disk) ────────────────────────────────────────

class GlobalLedger:
    """Persists successful query count across all runs."""

    def __init__(self, path: Path):
        self.path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            with open(self.path) as f:
                return json.load(f)
        return {"successful_queries": 0, "runs": []}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    @property
    def successful_queries(self) -> int:
        return self._data["successful_queries"]

    def record_run(self, run_id: str, n_successful: int, n_queries: int) -> None:
        self._data["successful_queries"] += n_successful
        self._data["runs"].append({
            "run_id": run_id,
            "successful_queries": n_successful,
            "total_queries": n_queries,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        self._save()


# ── Per-run adapter ───────────────────────────────────────────────────────────

class SerperAdapter:
    """One adapter instance per report run. Thread-safe for sequential use."""

    def __init__(
        self,
        run_id: str,
        global_ledger: GlobalLedger,
        raw_dir: Path,
    ):
        self.run_id = run_id
        self._global = global_ledger
        self._raw_dir = raw_dir
        self._raw_dir.mkdir(parents=True, exist_ok=True)

        self._run_queries: int = 0           # total queries fired this run
        self._run_success: int = 0           # successful (non-empty) queries
        self._unique_urls: set[str] = set()
        self._search_log: list[dict] = []    # full trace saved to disk

    # ── Public interface ──────────────────────────────────────────────────────

    async def search(self, queries: list[str]) -> str:
        """Execute queries against Serper, enforce caps, return formatted string."""
        api_key = os.environ.get("SERPER_API_KEY", "")
        if not api_key:
            return "ERROR: SERPER_API_KEY not set."

        # Pre-call cap checks
        remaining = QUERIES_PER_REPORT_MAX - self._run_queries
        if remaining <= 0:
            return f"QUERY_CAP_EXCEEDED: Report limit of {QUERIES_PER_REPORT_MAX} queries reached."

        if self._global.successful_queries + len(queries) > GLOBAL_QUERY_HARD_STOP:
            return f"QUERY_CAP_EXCEEDED: Global hard stop of {GLOBAL_QUERY_HARD_STOP} queries reached."

        queries = queries[:remaining]

        # Execute queries in parallel
        results = await asyncio.gather(
            *[self._call_serper(q, api_key) for q in queries],
            return_exceptions=True,
        )

        # Normalize and format
        formatted_parts: list[str] = []
        source_idx = 1
        for query, result in zip(queries, results):
            self._run_queries += 1
            if isinstance(result, Exception):
                self._search_log.append({
                    "query": query, "status": "error", "error": str(result),
                })
                continue

            organic = result.get("organic", [])[:RESULTS_PER_QUERY_MAX]
            if not organic:
                self._search_log.append({"query": query, "status": "empty_organic"})
                continue

            self._run_success += 1
            normalized: list[dict] = []
            for rank, item in enumerate(organic, 1):
                url = item.get("link", "")
                if url in self._unique_urls:
                    continue
                if len(self._unique_urls) >= UNIQUE_URLS_PER_REPORT_MAX:
                    break
                self._unique_urls.add(url)
                domain = urlparse(url).netloc
                norm = {
                    "query": query,
                    "title": item.get("title", ""),
                    "link": url,
                    "domain": domain,
                    "rank": rank,
                    "snippet": item.get("snippet", ""),
                }
                normalized.append(norm)
                formatted_parts.append(
                    f"\n\n--- SOURCE {source_idx}: {norm['title']} ---\n"
                    f"URL: {url}\n\n"
                    f"SUMMARY:\n{norm['snippet']}\n\n"
                    + "-" * 80
                )
                source_idx += 1

            self._search_log.append({
                "query": query,
                "status": "ok",
                "raw_response_path": self._save_raw(query, result),
                "normalized": normalized,
            })

        self._flush_log()
        if not formatted_parts:
            return "No valid search results found."
        return "Search results: \n" + "".join(formatted_parts)

    def ledger_snapshot(self) -> dict:
        return {
            "run_id": self.run_id,
            "run_queries_total": self._run_queries,
            "run_queries_success": self._run_success,
            "run_unique_urls": len(self._unique_urls),
            "global_successful_queries_before_run": self._global.successful_queries,
        }

    def finalize(self) -> None:
        """Call after the run completes to record in the global ledger."""
        self._global.record_run(self.run_id, self._run_success, self._run_queries)

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _call_serper(self, query: str, api_key: str) -> dict[str, Any]:
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": RESULTS_PER_QUERY_MAX}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                _SERPER_URL, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=SEARCH_TIMEOUT_SEC),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Serper HTTP {resp.status}: {text[:200]}")
                return await resp.json()

    def _save_raw(self, query: str, data: dict) -> str:
        safe = "".join(c if c.isalnum() else "_" for c in query)[:40]
        fname = f"{self.run_id}_{safe}_{int(time.time()*1000)}.json"
        path = self._raw_dir / fname
        with open(path, "w") as f:
            json.dump({"query": query, "response": data}, f, ensure_ascii=False)
        return str(path)

    def _flush_log(self) -> None:
        log_path = self._raw_dir / f"{self.run_id}_search_log.json"
        with open(log_path, "w") as f:
            json.dump(self._search_log, f, indent=2, ensure_ascii=False)


# ── Monkey-patch injection ────────────────────────────────────────────────────

def make_serper_tool(adapter: SerperAdapter):
    """Return a LangChain tool that delegates to the given SerperAdapter."""

    @tool(description=SERPER_SEARCH_DESCRIPTION)
    async def serper_search(
        queries: list[str],
        max_results: Annotated[int, InjectedToolArg] = RESULTS_PER_QUERY_MAX,
        topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
        config: RunnableConfig = None,
    ) -> str:
        return await adapter.search(queries)

    return serper_search


def patch_search(adapter: SerperAdapter):
    """Monkey-patch get_search_tool so SearchAPI.TAVILY routes to Serper."""
    import open_deep_research.utils as _odr_utils
    from open_deep_research.configuration import SearchAPI

    _orig = _odr_utils.get_search_tool

    async def _patched(search_api):
        if search_api == SearchAPI.TAVILY:
            return [make_serper_tool(adapter)]
        return await _orig(search_api)

    _odr_utils.get_search_tool = _patched
    return _orig  # return original so caller can restore


def restore_search(original) -> None:
    import open_deep_research.utils as _odr_utils
    _odr_utils.get_search_tool = original
