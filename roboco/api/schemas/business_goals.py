"""API request/response schemas for the Business Goals charter (INTENT.md §9)."""

from datetime import datetime
from typing import TYPE_CHECKING
from typing import cast as typing_cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from roboco.models.business_goals import Objective, OperatingPolicy

if TYPE_CHECKING:
    from roboco.db.tables import BusinessGoalsTable


class BusinessGoalsResponse(BaseModel):
    id: UUID
    north_star: str
    objectives: list[Objective]
    operating_policy: OperatingPolicy
    constraints: list[str]
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BusinessGoalsUpdateRequest(BaseModel):
    """Patch request — all fields optional, only present ones are applied."""

    north_star: str | None = None
    objectives: list[Objective] | None = None
    operating_policy: OperatingPolicy | None = None
    constraints: list[str] | None = None


def business_goals_to_response(goals: "BusinessGoalsTable") -> BusinessGoalsResponse:
    return BusinessGoalsResponse(
        id=typing_cast("UUID", goals.id),
        north_star=str(goals.north_star),
        objectives=[Objective.model_validate(o) for o in goals.objectives],
        operating_policy=OperatingPolicy.model_validate(goals.operating_policy),
        constraints=list(goals.constraints),
        created_at=goals.created_at,
        updated_at=goals.updated_at,
    )
