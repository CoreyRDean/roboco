"""External web & market research (INTENT.md §5 taxonomy, spec 02-web-research).

The company's only window onto the real world. ``ResearchService`` wraps a
**pluggable** web-search + fetch capability behind a small provider interface
and returns normalized, **cited** results (title, url, snippet). This is the
single place external research HTTP lives.

Two design rules drive everything here:

- **Graceful degradation.** If no provider/key is configured, the service does
  not raise and does not hard-fail — ``web_search``/``web_fetch`` return a
  structured result that plainly states "no search provider configured". A
  company missing a search key still runs; it just reports the gap.
- **Cost-bound breadth.** ``top_k`` is capped (``search_top_k_max``), the fetch
  body is byte-capped (``search_fetch_max_bytes``), and every HTTP call carries
  a timeout (``search_timeout_seconds``). Research observes the world cheaply
  and cannot run away.

Findings are persisted as durable, cited artifacts by reusing the existing
note/evidence path (``content_actions.note``) — no new table. ``format_finding``
renders a search response (with sources) into a ``note(scope="note")`` payload
the gateway already knows how to write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

import httpx
import structlog

from roboco.config import settings
from roboco.services.base import BaseService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


# =============================================================================
# RESULT SHAPES (normalized, cited)
# =============================================================================


@dataclass(frozen=True)
class CitedResult:
    """One cited search hit. ``url`` is the citation anchor."""

    title: str
    url: str
    snippet: str

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


@dataclass(frozen=True)
class SearchResponse:
    """Result of a ``web_search``. Always returned — never raised.

    ``degraded`` is True when no provider answered (unconfigured or an error);
    ``note`` carries the human-readable reason so a finding can state the gap
    rather than fill it.
    """

    query: str
    results: list[CitedResult] = field(default_factory=list)
    provider: str | None = None
    degraded: bool = False
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "provider": self.provider,
            "degraded": self.degraded,
            "note": self.note,
            "result_count": len(self.results),
        }


@dataclass(frozen=True)
class FetchResponse:
    """Result of a ``web_fetch``. Always returned — never raised.

    ``text`` is the extracted page text, truncated to the byte cap.
    ``truncated`` flags that the cap clipped the body.
    """

    url: str
    title: str = ""
    text: str = ""
    truncated: bool = False
    provider: str | None = None
    degraded: bool = False
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "truncated": self.truncated,
            "provider": self.provider,
            "degraded": self.degraded,
            "note": self.note,
            "char_count": len(self.text),
        }


# =============================================================================
# PLUGGABLE PROVIDER INTERFACE
# =============================================================================

_NO_PROVIDER_NOTE = (
    "no search provider configured — set ROBOCO_SEARCH_PROVIDER and "
    "ROBOCO_SEARCH_API_KEY to enable real web research"
)


@runtime_checkable
class SearchProvider(Protocol):
    """Pluggable external-research backend.

    A provider does the actual web I/O and normalizes into ``CitedResult`` /
    ``FetchResponse``. Implementations must never raise on a routine failure
    (no key, network error, bad status) — they return a ``degraded`` response
    with a ``note`` so the service stays graceful end to end.
    """

    name: str

    async def web_search(self, query: str, top_k: int) -> SearchResponse: ...

    async def web_fetch(self, url: str, max_bytes: int) -> FetchResponse: ...


class NullProvider:
    """Graceful-degradation provider used when nothing is configured.

    Every call returns a structured "no search provider configured" result.
    This is what makes missing-key the soft, surfaced state the spec requires
    rather than a hard failure.
    """

    name = "none"

    async def web_search(self, query: str, top_k: int) -> SearchResponse:
        _ = top_k
        return SearchResponse(
            query=query, provider=self.name, degraded=True, note=_NO_PROVIDER_NOTE
        )

    async def web_fetch(self, url: str, max_bytes: int) -> FetchResponse:
        _ = max_bytes
        return FetchResponse(
            url=url, provider=self.name, degraded=True, note=_NO_PROVIDER_NOTE
        )


class TavilyProvider:
    """Default HTTP provider (Tavily search API).

    Tavily is a search API purpose-built for LLM/agent research: a single POST
    returns cited results plus an optional page-content extract, which maps
    cleanly onto our ``web_search`` / ``web_fetch`` surface. Selected when
    ``ROBOCO_SEARCH_PROVIDER=tavily`` and a key is set. Any failure degrades
    gracefully instead of raising.
    """

    name = "tavily"
    _DEFAULT_BASE_URL: ClassVar[str] = "https://api.tavily.com"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or self._DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout

    async def web_search(self, query: str, top_k: int) -> SearchResponse:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/search",
                    json={
                        "api_key": self._api_key,
                        "query": query,
                        "max_results": top_k,
                        "search_depth": "basic",
                    },
                )
        except httpx.HTTPError as exc:
            return self._degraded_search(query, f"search request failed: {exc}")
        if not resp.is_success:
            return self._degraded_search(
                query, f"search provider returned HTTP {resp.status_code}"
            )
        return self._parse_search(query, resp.json(), top_k)

    def _parse_search(
        self, query: str, data: dict[str, Any], top_k: int
    ) -> SearchResponse:
        raw = data.get("results") or []
        results = [
            CitedResult(
                title=str(item.get("title") or item.get("url") or "").strip(),
                url=str(item.get("url") or "").strip(),
                snippet=str(item.get("content") or "").strip(),
            )
            for item in raw[:top_k]
            if item.get("url")
        ]
        note = None if results else "provider returned no results for this query"
        return SearchResponse(
            query=query,
            results=results,
            provider=self.name,
            degraded=False,
            note=note,
        )

    def _degraded_search(self, query: str, reason: str) -> SearchResponse:
        logger.warning("web_search degraded", provider=self.name, reason=reason)
        return SearchResponse(
            query=query, provider=self.name, degraded=True, note=reason
        )

    async def web_fetch(self, url: str, max_bytes: int) -> FetchResponse:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/extract",
                    json={"api_key": self._api_key, "urls": [url]},
                )
        except httpx.HTTPError as exc:
            return self._degraded_fetch(url, f"fetch request failed: {exc}")
        if not resp.is_success:
            return self._degraded_fetch(
                url, f"fetch provider returned HTTP {resp.status_code}"
            )
        return self._parse_fetch(url, resp.json(), max_bytes)

    def _parse_fetch(
        self, url: str, data: dict[str, Any], max_bytes: int
    ) -> FetchResponse:
        results = data.get("results") or []
        if not results:
            return self._degraded_fetch(
                url, "provider returned no content for this url"
            )
        first = results[0]
        raw_text = str(first.get("raw_content") or first.get("content") or "")
        clipped = raw_text.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
        return FetchResponse(
            url=str(first.get("url") or url),
            title=str(first.get("title") or "").strip(),
            text=clipped,
            truncated=len(clipped) < len(raw_text),
            provider=self.name,
            degraded=False,
        )

    def _degraded_fetch(self, url: str, reason: str) -> FetchResponse:
        logger.warning("web_fetch degraded", provider=self.name, reason=reason)
        return FetchResponse(url=url, provider=self.name, degraded=True, note=reason)


# Provider registry. Add a provider class here and select it via
# ROBOCO_SEARCH_PROVIDER. Each entry is a (name -> builder) where the builder
# takes the resolved settings and returns a configured SearchProvider.
_PROVIDER_BUILDERS: dict[str, Any] = {
    TavilyProvider.name: lambda key, base, timeout: TavilyProvider(
        api_key=key, base_url=base, timeout=timeout
    ),
}


def _build_provider() -> SearchProvider:
    """Select and build the configured provider, or the NullProvider.

    Graceful by construction: an unknown provider id or a missing key falls
    back to ``NullProvider`` (which degrades on every call) rather than raising
    at import/spawn time.
    """
    name = (settings.search_provider or "").strip().lower()
    if not name:
        return NullProvider()
    builder = _PROVIDER_BUILDERS.get(name)
    if builder is None:
        logger.warning(
            "unknown search provider configured; degrading",
            provider=name,
            known=sorted(_PROVIDER_BUILDERS),
        )
        return NullProvider()
    if not settings.search_api_key:
        logger.warning("search provider set but no API key; degrading", provider=name)
        return NullProvider()
    return builder(  # type: ignore[no-any-return]
        settings.search_api_key,
        settings.search_base_url,
        settings.search_timeout_seconds,
    )


# =============================================================================
# SERVICE
# =============================================================================


class ResearchService(BaseService):
    """External research: cost-bounded, cited web search + fetch.

    Subclasses ``BaseService`` for the standard service shape, but the search
    and fetch verbs are stateless (no DB), so ``session`` is optional — pass
    ``None`` from a context that has no DB (e.g. the MCP bridge). The DB session
    is only needed when a caller also wants to persist a finding through a
    session-bound service; the ``format_finding`` helper itself is pure.
    """

    service_name: ClassVar[str] = "research"

    def __init__(
        self,
        session: AsyncSession | None = None,
        provider: SearchProvider | None = None,
    ) -> None:
        # BaseService stores `self.session`; passing None is valid because the
        # research verbs are stateless. We deliberately don't call super() with
        # a real session requirement.
        self.session = session  # type: ignore[assignment]
        self.log = logger.bind(service=self.service_name)
        self._provider: SearchProvider = provider or _build_provider()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def _bounded_top_k(self, top_k: int) -> int:
        """Clamp ``top_k`` into [1, search_top_k_max] (cost bound)."""
        return max(1, min(int(top_k), settings.search_top_k_max))

    async def web_search(self, query: str, top_k: int = 5) -> SearchResponse:
        """Cited web search. Never raises; degrades to a structured result.

        ``top_k`` is clamped to ``search_top_k_max``. An empty query short-
        circuits to a degraded response so the provider is never billed for it.
        """
        cleaned = query.strip()
        if not cleaned:
            return SearchResponse(
                query=query,
                provider=self._provider.name,
                degraded=True,
                note="empty query — provide a search query",
            )
        bounded = self._bounded_top_k(top_k)
        try:
            return await self._provider.web_search(cleaned, bounded)
        except Exception as exc:  # last-resort guard — never hard-fail research
            self.log.warning("web_search unexpected error", error=str(exc))
            return SearchResponse(
                query=cleaned,
                provider=self._provider.name,
                degraded=True,
                note=f"search failed: {exc}",
            )

    async def web_fetch(self, url: str) -> FetchResponse:
        """Fetch and extract one page's text. Never raises; byte-capped.

        The body is capped at ``search_fetch_max_bytes`` (cost bound). An empty
        or non-http(s) URL short-circuits to a degraded response.
        """
        cleaned = url.strip()
        if not cleaned or not cleaned.lower().startswith(("http://", "https://")):
            return FetchResponse(
                url=url,
                provider=self._provider.name,
                degraded=True,
                note="invalid url — provide an absolute http(s) URL",
            )
        try:
            return await self._provider.web_fetch(
                cleaned, settings.search_fetch_max_bytes
            )
        except Exception as exc:  # last-resort guard — never hard-fail research
            self.log.warning("web_fetch unexpected error", error=str(exc))
            return FetchResponse(
                url=cleaned,
                provider=self._provider.name,
                degraded=True,
                note=f"fetch failed: {exc}",
            )


# =============================================================================
# PERSISTENCE (2.A2) — durable, cited artifacts via the existing note path
# =============================================================================


@dataclass(frozen=True)
class FindingNote:
    """A research finding rendered for the existing ``note`` path.

    No new table: a finding is recorded as a journal note with citations
    inline. Pass ``text`` + ``scope`` straight into
    ``ContentActions.note(agent_id=..., text=text, scope=scope, task_id=...)``.
    ``sources`` is the de-duplicated citation list, surfaced for callers that
    want the URLs structured (e.g. evidence assembly) without re-parsing text.
    """

    text: str
    scope: str
    sources: list[str]

    def as_note_kwargs(self) -> dict[str, Any]:
        """Keyword args for ``ContentActions.note`` (sans agent_id/task_id)."""
        return {"text": self.text, "scope": self.scope}


def _render_sources(results: list[CitedResult]) -> tuple[str, list[str]]:
    """Render a cited source list as markdown; return (markdown, urls)."""
    lines: list[str] = []
    urls: list[str] = []
    seen: set[str] = set()
    for r in results:
        if not r.url or r.url in seen:
            continue
        seen.add(r.url)
        urls.append(r.url)
        title = r.title or r.url
        line = f"- [{title}]({r.url})"
        if r.snippet:
            line += f" — {r.snippet}"
        lines.append(line)
    return "\n".join(lines), urls


def format_finding(
    *,
    summary: str,
    search: SearchResponse,
    scope: str = "note",
) -> FindingNote:
    """Format a research finding (summary + its sources) for the note path.

    The output is a grounded, cited artifact (spec 02): a short summary
    followed by a ``Sources`` block of clickable citations. When the search
    degraded (no provider, no results), that gap is stated in the body rather
    than filled in — keeping the finding honest.

    Reuses the existing journal/evidence path: hand ``as_note_kwargs()`` (plus
    the caller's ``agent_id``/``task_id``) to ``ContentActions.note``. No new
    persistence surface is introduced.
    """
    sources_md, urls = _render_sources(search.results)
    parts: list[str] = [summary.strip()] if summary.strip() else []
    parts.append(f"_Research query:_ `{search.query}`")
    if urls:
        parts.append(f"## Sources\n{sources_md}")
    else:
        gap = search.note or "no sources found"
        parts.append(f"## Sources\n_No citations — {gap}._")
    return FindingNote(text="\n\n".join(parts), scope=scope, sources=urls)


# =============================================================================
# FACTORY
# =============================================================================


def get_research_service(
    session: AsyncSession | None = None,
    provider: SearchProvider | None = None,
) -> ResearchService:
    """Build a ``ResearchService``.

    ``session`` is optional — the research verbs are stateless, so callers
    without a DB session (e.g. the MCP bridge) pass ``None``. ``provider`` is
    injectable for tests; production resolves it from settings.
    """
    return ResearchService(session=session, provider=provider)
