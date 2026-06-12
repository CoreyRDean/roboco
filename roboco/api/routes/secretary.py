"""Secretary routes — the CEO chief-of-staff read + relay surfaces.

The read endpoints (``/status``, ``/queue``, ``/digest``) are company-state the
Secretary fetches to brief the CEO; they are readable by any authenticated agent
(the Secretary agent reads them on the CEO's behalf). The write endpoints
(``/relay``, ``/goals``) carry CEO intent downward and are CEO-only — the
Secretary obeys the same gate list as the rest of the company (INTENT.md §6), so
a directive that would trip a gate becomes a CEO action item rather than a silent
execution. Goal reads reuse the existing ``GET /api/goals``.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from roboco.api.deps import CurrentAgentContext, DbSession
from roboco.api.schemas.business_goals import (
    BusinessGoalsResponse,
    business_goals_to_response,
)
from roboco.api.schemas.secretary import (
    GoalEditRequest,
    RelayRequest,
    RelayResponse,
)
from roboco.models.base import AgentRole
from roboco.services.secretary import get_secretary_service

router = APIRouter()


@router.get("/status")
async def get_status(
    db: DbSession,
    _agent: CurrentAgentContext,
) -> dict[str, Any]:
    """Compact company status: in-flight work by state, blockers, activity, spend."""
    service = get_secretary_service(db)
    return await service.status_summary()


@router.get("/queue")
async def get_queue(
    db: DbSession,
    _agent: CurrentAgentContext,
) -> dict[str, Any]:
    """The CEO action queue — pending approvals, Approve & Start, stranded work."""
    service = get_secretary_service(db)
    return await service.action_queue()


@router.get("/digest")
async def get_digest(
    db: DbSession,
    _agent: CurrentAgentContext,
) -> dict[str, Any]:
    """Proactive feed (3.A2): pending approvals, stale decisions, drift, pitches."""
    service = get_secretary_service(db)
    return await service.proactive_digest()


@router.post("/relay", response_model=RelayResponse)
async def relay_directive(
    data: RelayRequest,
    db: DbSession,
    agent: CurrentAgentContext,
) -> RelayResponse:
    """Carry a CEO directive downward — or gate it back as a CEO action item.

    CEO-only: this is the CEO speaking through the Secretary. Gated intents
    (spend, go_public, new_product_line, cap_breach) are never relayed silently.
    """
    if agent.role != AgentRole.CEO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the CEO can relay directives downward",
        )
    service = get_secretary_service(db)
    outcome = await service.relay_directive(
        ceo_agent_id=agent.agent_id,
        directive=data.directive,
        recipients=data.recipients,
    )
    return RelayResponse(
        executed=outcome.executed,
        gated=outcome.gated,
        gate=outcome.gate,
        recipients=outcome.recipients,
        detail=outcome.detail,
    )


@router.put("/goals", response_model=BusinessGoalsResponse)
async def apply_goal_edit(
    data: GoalEditRequest,
    db: DbSession,
    agent: CurrentAgentContext,
) -> BusinessGoalsResponse:
    """Apply a confirmed goal edit into the same artifact the Panel edits.

    CEO-only, mirroring ``PUT /api/goals`` — direction and the operating-policy
    leash are the CEO's to set. A convenience seam so a goal change the CEO makes
    conversationally lands in the singleton Business Goals charter.
    """
    if agent.role != AgentRole.CEO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the CEO can edit business goals",
        )
    service = get_secretary_service(db)
    goals = await service.apply_goal_edit(
        ceo_agent_id=agent.agent_id,
        north_star=data.north_star,
        objectives=data.objectives,
        operating_policy=data.operating_policy,
        constraints=data.constraints,
    )
    await db.commit()
    return business_goals_to_response(goals)
