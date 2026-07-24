"""Deterministic Serper search adapter for ``open_deep_research``.

The adapter keeps the upstream package untouched by replacing its Tavily tool at
runtime. It enforces the DRA search budget, emits machine-readable search
results for tracing, and records explicit failure codes without exposing API
credentials.

No request is made by importing this module. Network access occurs only when
``SerperAdapter.search`` is called with ``SERPER_API_KEY`` configured.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Annotated, Any, Iterator, Literal
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool

try:
    import fcntl
except ImportError:  # pragma: no cover - DRA runs on macOS/Linux.
    fcntl = None


QUERIES_PER_REPORT_MAX = 7
RESULTS_PER_QUERY_MAX = 3
UNIQUE_URLS_PER_REPORT_MAX = 15
GLOBAL_QUERY_HARD_STOP = 2400
SEARCH_TIMEOUT_SEC = 120

_SERPER_URL = "https://google.serper.dev/search"
_SEARCH_SCHEMA_VERSION = "dra_serper_search_v1"
_LEDGER_SCHEMA_VERSION = 1
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ACTIVE_ADAPTER: ContextVar[SerperAdapter | None] = ContextVar(
    "dra_active_serper_adapter",
    default=None,
)
_PATCH_LOCK = Lock()
_PATCH_REFCOUNT = 0
_PATCH_BASE: Any | None = None
_PATCH_DISPATCHER: Any | None = None

SERPER_SEARCH_DESCRIPTION = (
    "Search the web with Serper. Accepts a list of queries and returns normalized "
    "JSON containing query status plus title, link, domain, rank, and snippet for "
    "each selected organic source."
)


class FailureCode:
    """Stable failure codes written to tool output and trace logs."""

    MISSING_API_KEY = "missing_api_key"
    INVALID_QUERY = "invalid_query"
    REPORT_QUERY_CAP_EXCEEDED = "report_query_cap_exceeded"
    GLOBAL_QUERY_CAP_EXCEEDED = "global_query_cap_exceeded"
    HTTP_ERROR = "http_error"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    INVALID_JSON = "invalid_json"
    EMPTY_ORGANIC = "empty_organic"
    MALFORMED_ORGANIC = "malformed_organic"
    INTERNAL_ERROR = "internal_error"


class SerperRequestError(RuntimeError):
    """A Serper request failure with a stable, serializable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True)
class SearchPatchHandle:
    """State needed to restore a context-local search patch."""

    context_token: Token


def _utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_json_write(path: Path, data: Any) -> None:
    """Write JSON atomically so interrupted writes cannot corrupt a ledger."""
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


def _canonical_url(raw_url: str) -> str | None:
    """Return a fragment-free URL key, or ``None`` for invalid organic links."""
    raw_url = raw_url.strip()
    if not raw_url:
        return None
    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    hostname = parts.hostname.lower()
    if parts.port:
        hostname = f"{hostname}:{parts.port}"
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), hostname, path, parts.query, ""))


class GlobalLedger:
    """Process-safe global query ledger with conservative in-flight reservation.

    A query slot is reserved before a network request and settled immediately
    after the response. This prevents concurrent report runs from exceeding the
    2,400-success hard stop. A killed process can leave a conservative stale
    reservation, which blocks new calls rather than allowing an overshoot.
    """

    def __init__(self, path: Path):
        self.path = path
        self.lock_path = path.with_suffix(f"{path.suffix}.lock")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked_data() as data:
            self._validate(data)

    @staticmethod
    def _default_data() -> dict[str, Any]:
        return {
            "schema_version": _LEDGER_SCHEMA_VERSION,
            "successful_queries": 0,
            "reservations": {},
            "runs": [],
        }

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default_data()
        with open(self.path, encoding="utf-8") as handle:
            data = json.load(handle)
        # Migrate the initial adapter ledger without losing recorded usage.
        data.setdefault("schema_version", _LEDGER_SCHEMA_VERSION)
        data.setdefault("reservations", {})
        data.setdefault("runs", [])
        return data

    @staticmethod
    def _validate(data: dict[str, Any]) -> None:
        successful = data.get("successful_queries")
        reservations = data.get("reservations")
        runs = data.get("runs")
        if not isinstance(successful, int) or successful < 0:
            raise ValueError("Invalid global ledger: successful_queries")
        if successful > GLOBAL_QUERY_HARD_STOP:
            raise ValueError("Global ledger already exceeds the hard stop")
        if not isinstance(reservations, dict) or not isinstance(runs, list):
            raise ValueError("Invalid global ledger structure")

    @contextmanager
    def _locked_data(self) -> Iterator[dict[str, Any]]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "a+", encoding="utf-8") as lock_handle:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                data = self._read_unlocked()
                self._validate(data)
                yield data
                self._validate(data)
                _atomic_json_write(self.path, data)
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    @property
    def successful_queries(self) -> int:
        with self._locked_data() as data:
            return int(data["successful_queries"])

    def reserve(self, run_id: str, requested: int) -> tuple[str | None, int]:
        """Reserve up to ``requested`` possible successful query slots."""
        if requested <= 0:
            return None, 0
        with self._locked_data() as data:
            reserved = sum(
                int(item.get("count", 0))
                for item in data["reservations"].values()
            )
            available = max(
                0,
                GLOBAL_QUERY_HARD_STOP
                - int(data["successful_queries"])
                - reserved,
            )
            granted = min(requested, available)
            if granted == 0:
                return None, 0
            reservation_id = uuid.uuid4().hex
            data["reservations"][reservation_id] = {
                "run_id": run_id,
                "count": granted,
                "created_at": _utc_timestamp(),
            }
            return reservation_id, granted

    def settle(self, reservation_id: str | None, successful: int) -> None:
        """Commit successful queries and release the remainder of a reservation."""
        if reservation_id is None:
            if successful:
                raise ValueError("Cannot settle success without a reservation")
            return
        with self._locked_data() as data:
            reservation = data["reservations"].pop(reservation_id, None)
            if reservation is None:
                raise ValueError(f"Unknown ledger reservation: {reservation_id}")
            reserved = int(reservation["count"])
            if successful < 0 or successful > reserved:
                raise ValueError("Successful count exceeds reserved query slots")
            data["successful_queries"] += successful

    def record_run(self, run_id: str, snapshot: dict[str, Any]) -> None:
        """Upsert a finalized per-report summary without double counting."""
        record = {
            "run_id": run_id,
            "queries_requested": snapshot["run_queries_requested"],
            "queries_attempted": snapshot["run_queries_attempted"],
            "queries_successful": snapshot["run_queries_successful"],
            "queries_failed": snapshot["run_queries_failed"],
            "sources_selected": snapshot["run_sources_selected"],
            "unique_urls": snapshot["run_unique_urls"],
            "global_successful_queries_at_start": snapshot[
                "global_successful_queries_at_start"
            ],
            "global_successful_queries_at_finalize": snapshot[
                "global_successful_queries"
            ],
            "finalized_at": _utc_timestamp(),
        }
        with self._locked_data() as data:
            data["runs"] = [
                item for item in data["runs"] if item.get("run_id") != run_id
            ]
            data["runs"].append(record)
            data["runs"].sort(key=lambda item: str(item.get("run_id", "")))


class SerperAdapter:
    """One search adapter per report run."""

    def __init__(
        self,
        run_id: str,
        global_ledger: GlobalLedger,
        raw_dir: Path,
    ):
        if not _RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError(
                "run_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}"
            )
        self.run_id = run_id
        self._global = global_ledger
        self._raw_dir = raw_dir
        self._raw_dir.mkdir(parents=True, exist_ok=True)

        self._run_requested = 0
        self._run_attempted = 0
        self._run_success = 0
        self._run_failed = 0
        self._sources_selected = 0
        self._unique_urls: set[str] = set()
        self._search_log: list[dict[str, Any]] = []
        # Claim cursor for tracer reconciliation. Matching by query text (first
        # unclaimed) is robust when concurrent researchers finish out of order.
        self._claimed_sequences: set[int] = set()
        self._query_sequence = 0
        self._finalized = False
        self._global_success_at_start = self._global.successful_queries
        # Serialize tool invocations. Queries inside one tool call remain parallel.
        self._search_lock = asyncio.Lock()

    async def search(self, queries: list[str]) -> str:
        """Execute and normalize queries while enforcing all report/global caps."""
        if self._finalized:
            raise RuntimeError("Cannot search after adapter.finalize()")
        async with self._search_lock:
            return await self._search_serialized(queries)

    async def _search_serialized(self, queries: list[str]) -> str:
        requested = [
            (self._next_query_sequence(), query, invalid)
            for query, invalid in self._normalize_query_inputs(queries)
        ]
        self._run_requested += len(requested)
        records: list[dict[str, Any]] = []

        api_key = os.environ.get("SERPER_API_KEY", "").strip()
        if not api_key:
            for query_sequence, query, invalid in requested:
                records.append(
                    self._failure_record(
                        query,
                        FailureCode.INVALID_QUERY
                        if invalid
                        else FailureCode.MISSING_API_KEY,
                        attempted=False,
                        query_sequence=query_sequence,
                    )
                )
            self._commit_records(records)
            return self._serialize_tool_result(records)

        valid: list[tuple[int, str]] = []
        for query_sequence, query, invalid in requested:
            if invalid:
                records.append(
                    self._failure_record(
                        query,
                        FailureCode.INVALID_QUERY,
                        attempted=False,
                        query_sequence=query_sequence,
                    )
                )
            else:
                valid.append((query_sequence, query))

        report_remaining = max(
            0,
            QUERIES_PER_REPORT_MAX - self._run_attempted,
        )
        report_accepted = valid[:report_remaining]
        report_rejected = valid[report_remaining:]
        records.extend(
            self._failure_record(
                query,
                FailureCode.REPORT_QUERY_CAP_EXCEEDED,
                attempted=False,
                query_sequence=query_sequence,
            )
            for query_sequence, query in report_rejected
        )

        reservation_id, global_granted = self._global.reserve(
            self.run_id,
            len(report_accepted),
        )
        executable = report_accepted[:global_granted]
        global_rejected = report_accepted[global_granted:]
        records.extend(
            self._failure_record(
                query,
                FailureCode.GLOBAL_QUERY_CAP_EXCEEDED,
                attempted=False,
                query_sequence=query_sequence,
            )
            for query_sequence, query in global_rejected
        )
        self._run_attempted += len(executable)

        successful = 0
        try:
            if executable:
                timeout = aiohttp.ClientTimeout(total=SEARCH_TIMEOUT_SEC)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    responses = await asyncio.gather(
                        *[
                            self._call_serper(query, api_key, session)
                            for _, query in executable
                        ],
                        return_exceptions=True,
                    )
                for (query_sequence, query), response in zip(
                    executable,
                    responses,
                ):
                    record = self._response_record(
                        query,
                        response,
                        query_sequence=query_sequence,
                    )
                    records.append(record)
                    if record["status"] == "ok":
                        successful += 1
        finally:
            self._global.settle(reservation_id, successful)

        self._commit_records(records)
        return self._serialize_tool_result(records)

    @staticmethod
    def _normalize_query_inputs(queries: Any) -> list[tuple[str, bool]]:
        if isinstance(queries, str):
            queries = [queries]
        if not isinstance(queries, list):
            return [(str(queries), True)]
        normalized: list[tuple[str, bool]] = []
        for query in queries:
            if not isinstance(query, str):
                normalized.append((str(query), True))
                continue
            clean = " ".join(query.split())
            normalized.append((clean, not bool(clean)))
        return normalized

    async def _call_serper(
        self,
        query: str,
        api_key: str,
        session: aiohttp.ClientSession,
    ) -> dict[str, Any]:
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": RESULTS_PER_QUERY_MAX}
        try:
            async with session.post(
                _SERPER_URL,
                json=payload,
                headers=headers,
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise SerperRequestError(
                        FailureCode.HTTP_ERROR,
                        f"Serper HTTP {response.status}: {body[:200]}",
                        http_status=response.status,
                    )
                try:
                    data = await response.json()
                except (aiohttp.ContentTypeError, json.JSONDecodeError) as exc:
                    raise SerperRequestError(
                        FailureCode.INVALID_JSON,
                        f"Invalid Serper JSON: {exc}",
                        http_status=response.status,
                    ) from exc
        except asyncio.TimeoutError as exc:
            raise SerperRequestError(
                FailureCode.TIMEOUT,
                f"Serper request timed out after {SEARCH_TIMEOUT_SEC}s",
            ) from exc
        except aiohttp.ClientError as exc:
            raise SerperRequestError(
                FailureCode.NETWORK_ERROR,
                f"Serper network error: {exc}",
            ) from exc
        if not isinstance(data, dict):
            raise SerperRequestError(
                FailureCode.INVALID_JSON,
                "Serper response must be a JSON object",
            )
        return data

    def _response_record(
        self,
        query: str,
        response: Any,
        *,
        query_sequence: int,
    ) -> dict[str, Any]:
        if isinstance(response, BaseException):
            if isinstance(response, SerperRequestError):
                return self._failure_record(
                    query,
                    response.code,
                    attempted=True,
                    message=str(response),
                    http_status=response.http_status,
                    query_sequence=query_sequence,
                )
            return self._failure_record(
                query,
                FailureCode.INTERNAL_ERROR,
                attempted=True,
                message=f"{type(response).__name__}: {response}",
                query_sequence=query_sequence,
            )

        organic = response.get("organic")
        if not isinstance(organic, list) or not organic:
            return self._failure_record(
                query,
                FailureCode.EMPTY_ORGANIC,
                attempted=True,
                raw_response=response,
                query_sequence=query_sequence,
            )

        valid_sources: list[dict[str, Any]] = []
        for fallback_rank, item in enumerate(
            organic[:RESULTS_PER_QUERY_MAX],
            start=1,
        ):
            if not isinstance(item, dict):
                continue
            canonical_url = _canonical_url(str(item.get("link", "")))
            if canonical_url is None:
                continue
            rank = item.get("position", fallback_rank)
            if not isinstance(rank, int) or rank < 1:
                rank = fallback_rank
            valid_sources.append(
                {
                    "query": query,
                    "title": str(item.get("title", "")).strip(),
                    "link": canonical_url,
                    "domain": urlsplit(canonical_url).netloc,
                    "rank": rank,
                    "snippet": str(item.get("snippet", "")).strip(),
                }
            )

        if not valid_sources:
            return self._failure_record(
                query,
                FailureCode.MALFORMED_ORGANIC,
                attempted=True,
                raw_response=response,
                query_sequence=query_sequence,
            )

        selected: list[dict[str, Any]] = []
        for source in valid_sources:
            url = source["link"]
            if url in self._unique_urls:
                continue
            if len(self._unique_urls) >= UNIQUE_URLS_PER_REPORT_MAX:
                break
            self._unique_urls.add(url)
            selected.append(source)

        record = self._base_record(
            query,
            attempted=True,
            query_sequence=query_sequence,
        )
        record.update(
            {
                "status": "ok",
                "failure_code": None,
                "sources": selected,
                "raw_response": response,
            }
        )
        return record

    def _next_query_sequence(self) -> int:
        self._query_sequence += 1
        return self._query_sequence

    def _base_record(
        self,
        query: str,
        *,
        attempted: bool,
        query_sequence: int,
    ) -> dict[str, Any]:
        return {
            "query_sequence": query_sequence,
            "query": query,
            "attempted": attempted,
            "status": "failure",
            "failure_code": None,
            "http_status": None,
            "message": None,
            "sources": [],
        }

    def _failure_record(
        self,
        query: str,
        code: str,
        *,
        attempted: bool,
        message: str | None = None,
        http_status: int | None = None,
        raw_response: dict[str, Any] | None = None,
        query_sequence: int,
    ) -> dict[str, Any]:
        record = self._base_record(
            query,
            attempted=attempted,
            query_sequence=query_sequence,
        )
        record.update(
            {
                "failure_code": code,
                "http_status": http_status,
                "message": message,
            }
        )
        if raw_response is not None:
            record["raw_response"] = raw_response
        return record

    def _commit_records(self, records: list[dict[str, Any]]) -> None:
        for record in records:
            raw_response = record.pop("raw_response", None)
            if raw_response is not None:
                record["raw_response_path"] = self._save_raw(
                    record["query_sequence"],
                    record["query"],
                    raw_response,
                )
            if record["status"] == "ok":
                self._run_success += 1
            elif record["attempted"]:
                self._run_failed += 1
            self._sources_selected += len(record["sources"])
            self._search_log.append(record)
        self._search_log.sort(key=lambda item: item["query_sequence"])
        self._flush_log()

    def claim_records_for_queries(
        self,
        queries: list[str],
    ) -> list[dict[str, Any] | None]:
        """Claim unconsumed search records matching tool-call queries in order.

        Matching is first-unclaimed by exact query string. This remains correct
        when concurrent researchers emit ``on_tool_end`` out of completion order.
        """
        claimed: list[dict[str, Any] | None] = []
        for query in queries:
            match: dict[str, Any] | None = None
            for record in self._search_log:
                sequence = int(record["query_sequence"])
                if sequence in self._claimed_sequences:
                    continue
                if record["query"] != query:
                    continue
                self._claimed_sequences.add(sequence)
                match = {
                    "query_sequence": sequence,
                    "query": record["query"],
                    "attempted": record["attempted"],
                    "status": record["status"],
                    "failure_code": record["failure_code"],
                    "sources": list(record["sources"]),
                }
                break
            claimed.append(match)
        return claimed

    def _save_raw(
        self,
        query_sequence: int,
        query: str,
        response: dict[str, Any],
    ) -> str:
        path = self._raw_dir / (
            f"{self.run_id}_query_{query_sequence:03d}.json"
        )
        _atomic_json_write(
            path,
            {"query": query, "response": response},
        )
        return str(path)

    def _flush_log(self) -> None:
        path = self._raw_dir / f"{self.run_id}_search_log.json"
        _atomic_json_write(
            path,
            {
                "schema_version": _SEARCH_SCHEMA_VERSION,
                "run_id": self.run_id,
                "queries": self._search_log,
                "ledger": self.ledger_snapshot(),
            },
        )

    @staticmethod
    def _serialize_tool_result(records: list[dict[str, Any]]) -> str:
        """Machine-readable payload used by tests and offline replay."""
        records = sorted(
            records,
            key=lambda record: record["query_sequence"],
        )
        successes = sum(record["status"] == "ok" for record in records)
        if successes == len(records) and records:
            status = "ok"
        elif successes:
            status = "partial_failure"
        else:
            status = "failure"
        payload = {
            "schema_version": _SEARCH_SCHEMA_VERSION,
            "status": status,
            "queries": records,
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def format_for_model(records: list[dict[str, Any]]) -> str:
        """Tavily-like text the researcher LLM can cite; no credentials."""
        records = sorted(records, key=lambda item: item["query_sequence"])
        blocks: list[str] = []
        source_index = 0
        for record in records:
            for source in record.get("sources") or []:
                source_index += 1
                title = source.get("title") or "(untitled)"
                link = source.get("link") or ""
                snippet = source.get("snippet") or ""
                blocks.append(
                    f"\n\n--- SOURCE {source_index}: {title} ---\n"
                    f"URL: {link}\n\n"
                    f"SUMMARY:\n{snippet}\n\n"
                    + ("-" * 80)
                )
        if blocks:
            return "Search results: \n" + "".join(blocks)

        # No selected sources: surface explicit failure codes so the model can retry.
        failures = []
        for record in records:
            code = record.get("failure_code") or record.get("status") or "unknown"
            failures.append(f"- query={record.get('query')!r} failure_code={code}")
        detail = "\n".join(failures) if failures else "- no queries executed"
        return (
            "No valid search results found. Please try different search queries "
            "or use a different search API.\n"
            f"Adapter diagnostics:\n{detail}"
        )

    def ledger_snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_queries_requested": self._run_requested,
            "run_queries_attempted": self._run_attempted,
            "run_queries_successful": self._run_success,
            "run_queries_failed": self._run_failed,
            "run_sources_selected": self._sources_selected,
            "run_unique_urls": len(self._unique_urls),
            "global_successful_queries_at_start": self._global_success_at_start,
            "global_successful_queries": self._global.successful_queries,
            "report_query_cap": QUERIES_PER_REPORT_MAX,
            "report_unique_url_cap": UNIQUE_URLS_PER_REPORT_MAX,
            "global_query_hard_stop": GLOBAL_QUERY_HARD_STOP,
        }

    def finalize(self) -> None:
        """Persist an idempotent report summary in the global ledger."""
        if self._finalized:
            return
        self._global.record_run(self.run_id, self.ledger_snapshot())
        self._finalized = True


def make_serper_tool(adapter: SerperAdapter):
    """Return the LangChain search tool expected by open_deep_research.

    The tool name stays ``serper_search`` (bound tools list is the authority for
    the model). Return text is Tavily-shaped for the researcher LLM; structured
    records are recovered by the tracer via ``pop_trace_batch``.
    """

    @tool(description=SERPER_SEARCH_DESCRIPTION)
    async def serper_search(
        queries: list[str],
        max_results: Annotated[int, InjectedToolArg] = RESULTS_PER_QUERY_MAX,
        topic: Annotated[
            Literal["general", "news", "finance"],
            InjectedToolArg,
        ] = "general",
        config: RunnableConfig = None,
    ) -> str:
        del max_results, topic, config
        payload = json.loads(await adapter.search(queries))
        return SerperAdapter.format_for_model(payload.get("queries") or [])

    serper_search.metadata = {
        **(serper_search.metadata or {}),
        "type": "search",
        "name": "web_search",
    }
    return serper_search


def patch_search(adapter: SerperAdapter):
    """Route Tavily to a context-local Serper adapter.

    Context-local dispatch prevents parallel report tasks from sending searches
    to another report's adapter while retaining the upstream monkey-patch API.
    """
    import open_deep_research.utils as odr_utils
    from open_deep_research.configuration import SearchAPI

    global _PATCH_BASE, _PATCH_DISPATCHER, _PATCH_REFCOUNT
    with _PATCH_LOCK:
        if _PATCH_REFCOUNT == 0:
            _PATCH_BASE = odr_utils.get_search_tool

            async def dispatcher(search_api):
                active = _ACTIVE_ADAPTER.get()
                if active is not None and search_api == SearchAPI.TAVILY:
                    return [make_serper_tool(active)]
                return await _PATCH_BASE(search_api)

            _PATCH_DISPATCHER = dispatcher
            odr_utils.get_search_tool = dispatcher
        elif odr_utils.get_search_tool is not _PATCH_DISPATCHER:
            raise RuntimeError("open_deep_research search factory changed while patched")
        _PATCH_REFCOUNT += 1
    token = _ACTIVE_ADAPTER.set(adapter)
    return SearchPatchHandle(context_token=token)


def restore_search(handle: SearchPatchHandle) -> None:
    """Restore this context and unpatch upstream after the final active run."""
    import open_deep_research.utils as odr_utils

    global _PATCH_BASE, _PATCH_DISPATCHER, _PATCH_REFCOUNT
    _ACTIVE_ADAPTER.reset(handle.context_token)
    with _PATCH_LOCK:
        if _PATCH_REFCOUNT <= 0:
            raise RuntimeError("restore_search called without an active patch")
        _PATCH_REFCOUNT -= 1
        if _PATCH_REFCOUNT == 0:
            if odr_utils.get_search_tool is _PATCH_DISPATCHER:
                odr_utils.get_search_tool = _PATCH_BASE
            _PATCH_BASE = None
            _PATCH_DISPATCHER = None
