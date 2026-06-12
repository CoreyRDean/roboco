"""Business Goals routes — the single CEO-editable company charter (INTENT.md §9).

GET is readable by any authenticated agent (every agent orients to the charter);
PUT is CEO-only — direction and the operating-policy leash are the CEO's to set.
"""

from fastapi import APIRouter, HTTPException, status

from roboco.api.deps import CurrentAgentContext, DbSession
from roboco.api.schemas.business_goals import (
    BusinessGoalsResponse,
    BusinessGoalsUpdateRequest,
    business_goals_to_response,
)
from roboco.models.base import AgentRole
from roboco.models.business_goals import BusinessGoalsUpdate
from roboco.services.business_goals import get_business_goals_service

router = APIRouter()


@router.get("", response_model=BusinessGoalsResponse)
async def get_goals(
    db: DbSession,
    _agent: CurrentAgentContext,
) -> BusinessGoalsResponse:
    """Read the company charter. Any authenticated agent orients to it."""
    service = get_business_goals_service(db)
    goals = await service.get_or_initialize()
    return business_goals_to_response(goals)


@router.put("", response_model=BusinessGoalsResponse)
async def update_goals(
    data: BusinessGoalsUpdateRequest,
    db: DbSession,
    agent: CurrentAgentContext,
) -> BusinessGoalsResponse:
    """Revise the charter. CEO-only — this is the company's direction and leash."""
    if agent.role != AgentRole.CEO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CEO can edit business goals",
        )
    service = get_business_goals_service(db)
    update = BusinessGoalsUpdate(
        north_star=data.north_star,
        objectives=data.objectives,
        operating_policy=data.operating_policy,
        constraints=data.constraints,
    )
    goals = await service.update(update, updated_by=agent.agent_id)
    await db.commit()
    return business_goals_to_response(goals)
