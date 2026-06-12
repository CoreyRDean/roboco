"""roboco-search MCP server — external web-research tools (spec 02-web-research).

Forwards to ``/api/v1/research/*`` on the orchestrator. Tools are role-scoped at
*spawn* time: the orchestrator writes ``search_tools`` into the per-agent
manifest and we register only those names here. The orchestrator API gates the
research endpoints to the roles allowed to research (Board + main/cell PM) via
``require_research``, so an off-role caller gets a 403 rather than a result —
but per-agent registration also keeps the model from ever *seeing* the tools on
its palette when its role isn't research-capable.

This is the agent-facing half of the research capability: ``web_search`` and
``web_fetch`` are thin wrappers that POST to the gateway-internal endpoints,
which delegate to ``ResearchService`` (the single place external research HTTP
lives). The service never raises — a missing provider or a network error comes
back as a ``degraded`` evidence payload with a ``note`` stating the gap — so
these tools always return an ``Envelope.ok``: the agent reads the world or reads
the gap, and either way it gets a cited artifact to ground a finding on.

If the manifest is missing or unreadable (e.g. local test runs without the bind
mount) nothing is registered and a warning is logged — research tooling is
additive, so a missing manifest degrades to "no research tools" rather than
exposing them to every role.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import httpx
import structlog
from mcp.server.fastmcp import FastMCP

ORCHESTRATOR_URL = os.environ.get(
    "ROBOCO_ORCHESTRATOR_URL",
    "http://roboco-orchestrator:8000",
)
AGENT_ID = os.environ["ROBOCO_AGENT_ID"]
AGENT_ROLE = os.environ["ROBOCO_AGENT_ROLE"]

# Research reads the open web (search + a single page fetch), so it can be
# slower than the gateway loopback. Keep a generous-but-bounded timeout; the
# service itself caps breadth (top_k) and fetch size server-side.
_TIMEOUT = 30

mcp = FastMCP("roboco-search")
log = structlog.get_logger()


def _build_headers() -> dict[str, str]:
    """Build per-call headers including a fresh X-Correlation-ID.

    Mirrors flow_server / do_server: each MCP call mints its own correlation id
    so the orchestrator's middleware can bind it to structlog and the envelope
    echoes it back to the agent.
    """
    return {
        "X-Agent-ID": AGENT_ID,
        "X-Agent-Role": AGENT_ROLE,
        "X-Correlation-ID": str(uuid.uuid4()),
    }


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST a research request to the orchestrator and return the JSON envelope.

    Mirrors flow_server._post: surfaces the orchestrator's envelope on both
    2xx and 4xx so the agent always sees ``remediate`` even when its role is
    rejected (403) for the research endpoints. Only fabricates a
    ``transport_error`` envelope when the body is unparseable (e.g. a 5xx with
    an HTML error page or a network failure).

    There is no circuit breaker here: the research endpoints always answer
    ``Envelope.ok`` (the service degrades inside the evidence payload rather
    than rejecting), so there is no rejection kind for a per-verb breaker to
    count.
    """
    with httpx.Client(timeout=_TIMEOUT) as client:
        response = client.post(
            f"{ORCHESTRATOR_URL}{path}",
            headers=_build_headers(),
            json=body,
        )
        try:
            payload: dict[str, Any] = response.json()
        except (ValueError, json.JSONDecodeError):
            # No JSON body (HTML error page, empty body, etc). Surface the
            # status as a synthetic envelope so the agent gets a remediate
            # hint instead of a Python traceback.
            return {
                "error": "transport_error",
                "message": (
                    f"orchestrator returned HTTP {response.status_code}"
                    f" with no JSON body for {path}"
                ),
                "remediate": (
                    "check that the orchestrator is up and the route exists;"
                    " contact the human operator if this persists"
                ),
                "missing": [],
            }
    return payload


def web_search(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search the open web for a query; returns normalized, cited results.

    Use this to ground market / competitive / technology claims in real
    sources — never assert an unsourced market fact. The result is an
    ``Envelope`` whose ``evidence`` carries a list of ``{title, url, snippet}``
    hits you should cite. If research is unavailable (no provider configured,
    network error) the evidence comes back ``degraded`` with a ``note``
    explaining the gap — record the gap rather than inventing a fact.

    Args:
        query: What to search for. A focused, specific query returns better
            sources than a broad one.
        top_k: How many results to ask for. Clamped server-side to the cost
            bound (``search_top_k_max``), so an over-eager value degrades to
            the cap rather than erroring. Default 5.
    """
    return _post(
        "/api/v1/research/web_search",
        {"query": query, "top_k": top_k},
    )


def web_fetch(url: str) -> dict[str, Any]:
    """Fetch and extract the text of one web page; returns a cited artifact.

    Use this after ``web_search`` to read a specific source in depth before
    grounding a claim on it. The result is an ``Envelope`` whose ``evidence``
    carries the page ``url`` and its extracted text (byte-capped server-side).
    If the fetch fails the evidence comes back ``degraded`` with a ``note`` —
    cite the gap, not an invented detail.

    Args:
        url: The page to fetch. Pass a single concrete URL (typically one of
            the urls returned by ``web_search``).
    """
    return _post(
        "/api/v1/research/web_fetch",
        {"url": url},
    )


# ---------- Tool registry ----------
#
# Maps the tool name an agent calls (matches manifest entries and the
# orchestrator's API path segment) to the Python implementation.

_TOOLS: dict[str, Any] = {
    "web_search": web_search,
    "web_fetch": web_fetch,
}


def _load_manifest_search_tools() -> list[str] | None:
    """Read the spawn manifest and return its ``search_tools`` list.

    Returns ``None`` when the manifest is missing or unreadable so callers can
    fall back to registering nothing. Never raises.
    """
    manifest_path = Path(
        os.environ.get("ROBOCO_TOOL_MANIFEST_PATH", "/app/tool-manifest.json"),
    )
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning(
            "search_server: cannot read manifest",
            path=str(manifest_path),
            error=str(exc),
        )
        return None
    search_tools = manifest.get("search_tools")
    if not isinstance(search_tools, list):
        # A research-incapable role simply has no search_tools key — that's
        # expected, not an error. Only warn when the key is present but the
        # wrong shape.
        if "search_tools" in manifest:
            log.warning(
                "search_server: manifest search_tools is not a list",
                path=str(manifest_path),
            )
        return []
    return [str(tool) for tool in search_tools]


def _register_tools() -> list[str]:
    """Register MCP tools according to the manifest.

    Unlike flow_server / do_server, this server does NOT refuse to start on a
    missing manifest. Research tooling is additive and the gateway gates the
    endpoints by role server-side, so the safe failure mode is "register no
    search tools" rather than crashing the whole MCP boot.

    Returns the list of tool names actually registered.
    """
    allowed = _load_manifest_search_tools()
    if allowed is None:
        manifest_path = os.environ.get(
            "ROBOCO_TOOL_MANIFEST_PATH", "/app/tool-manifest.json"
        )
        log.warning(
            "search_server: manifest unavailable; registering no search tools",
            role=AGENT_ROLE,
            path=manifest_path,
        )
        return []
    unknown = [tool for tool in allowed if tool not in _TOOLS]
    if unknown:
        log.warning(
            "search_server: manifest references unknown search tools",
            role=AGENT_ROLE,
            missing=sorted(unknown),
        )
    names = [tool for tool in allowed if tool in _TOOLS]

    for tool in names:
        mcp.tool(name=tool)(_TOOLS[tool])
    log.info(
        "search_server: registered tools",
        role=AGENT_ROLE,
        tools=sorted(names),
    )
    return names


_REGISTERED_TOOLS = _register_tools()


if __name__ == "__main__":
    mcp.run()
