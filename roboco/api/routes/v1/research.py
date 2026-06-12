"""External-research HTTP endpoints (spec 02-web-research, item 2.B1).

Gateway-internal bridge the ``roboco-search`` MCP server POSTs to. Thin
handlers: delegate to ``ResearchService`` (the single place external research
HTTP lives) and wrap its normalized, cited result into the standard
``Envelope`` every gateway verb returns.

The service never raises and never hard-fails — a missing provider or a
network error comes back as a ``degraded`` result with a ``note`` stating the
gap. So these endpoints always answer ``Envelope.ok``: "research succeeded" vs
"research is unavailable, here's why" is carried *inside* the evidence payload
(``degraded`` / ``note``), not as an HTTP error. The agent reads the world or
reads the gap; either way it gets a cited artifact it can ground a finding on.

Gated to roles allowed to research (Board + main/cell PM) via ``require_research``.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from roboco.api.deps import get_research_service
from roboco.api.routes.v1._role_dep import envelope_to_response, require_research
from roboco.api.schemas.v1.research import WebFetchRequest, WebSearchRequest
from roboco.services.gateway.envelope import Envelope
from roboco.services.research import ResearchService

router = APIRouter(
    prefix="/api/v1/research",
    tags=["v1-research"],
    dependencies=[require_research],
)


_ResearchServiceDep = Annotated[ResearchService, Depends(get_research_service)]


@router.post("/web_search")
async def web_search(
    request: Request,
    body: WebSearchRequest,
    research: _ResearchServiceDep,
) -> dict:
    response = await research.web_search(body.query, top_k=body.top_k)
    env = Envelope.ok(
        status="research_complete",
        next="cite the sources in a note(scope='note') on the task",
        evidence=response.to_dict(),
    )
    return envelope_to_response(env, request)


@router.post("/web_fetch")
async def web_fetch(
    request: Request,
    body: WebFetchRequest,
    research: _ResearchServiceDep,
) -> dict:
    response = await research.web_fetch(body.url)
    env = Envelope.ok(
        status="research_complete",
        next="cite the source url in a note(scope='note') on the task",
        evidence=response.to_dict(),
    )
    return envelope_to_response(env, request)
