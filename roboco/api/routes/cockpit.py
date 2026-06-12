"""Cockpit routes — the CEO watch-surface derived state (specs/06-cockpit.md).

The cockpit answers three questions: *Is the business winning? What is happening
now? What needs me?* This route serves the first — a single read-only derived
``GET /summary`` that composes already-built services (Business Goals, the
Secretary's drift signal, ``UsageService`` spend projection, the
``ProductService`` active-product count) into the "winning?" snapshot. No new
measurement machinery; the cockpit is legibility, not autonomy (spec §Boundaries).

Honest boundary (spec §"On winning"): every performance number is labelled
``proxy`` until real external launches are greenlit — the cockpit does not
pretend to measure revenue that isn't there.

Read-only and readable by any authenticated agent (the panel/Secretary fetch it
on the CEO's behalf), mirroring the Secretary read surfaces.
"""

from fastapi import APIRouter

from roboco.api.deps import CurrentAgentContext, DbSession
from roboco.api.schemas.cockpit import CockpitSummaryResponse
from roboco.services.secretary import get_secretary_service

router = APIRouter()


@router.get("/summary", response_model=CockpitSummaryResponse)
async def get_summary(
    db: DbSession,
    _agent: CurrentAgentContext,
) -> CockpitSummaryResponse:
    """Derived cockpit state: per-objective progress, goal-coverage + drift,
    spend vs budget, and active products vs cap — composed read-only from
    existing services. Proxy metrics until real external launches (spec).
    """
    service = get_secretary_service(db)
    summary = await service.cockpit_summary()
    return CockpitSummaryResponse.model_validate(summary)
