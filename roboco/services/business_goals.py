"""BusinessGoalsService — the singleton CEO charter (INTENT.md §9).

One row, fixed primary key. ``get_or_initialize`` returns it, lazily seeding
the row from model defaults if the migration has not yet run (e.g. a test DB
built via ``create_all``). ``update`` applies patch semantics from a
``BusinessGoalsUpdate`` DTO. Read by the gateway and injected into every
agent briefing.
"""

from typing import ClassVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from roboco.db.tables import BusinessGoalsTable
from roboco.models.business_goals import (
    SINGLETON_ID,
    BusinessGoals,
    BusinessGoalsUpdate,
    OperatingPolicy,
)
from roboco.services.base import BaseService


class BusinessGoalsService(BaseService):
    service_name: ClassVar[str] = "business_goals"

    async def get(self) -> BusinessGoalsTable | None:
        result = await self.session.execute(
            select(BusinessGoalsTable).where(BusinessGoalsTable.id == SINGLETON_ID)
        )
        return result.scalar_one_or_none()

    async def get_or_initialize(self) -> BusinessGoalsTable:
        """Fetch the singleton charter, seeding it from defaults if absent.

        The migration seeds the row on a real DB; this fallback covers DBs
        built via ``Base.metadata.create_all`` (tests) and is a no-op once the
        row exists, so the charter is always present when an agent briefs.
        """
        goals = await self.get()
        if goals is not None:
            return goals
        defaults = BusinessGoals()
        goals = BusinessGoalsTable(
            id=SINGLETON_ID,
            north_star=defaults.north_star,
            constraints=list(defaults.constraints),
            objectives=[o.model_dump(mode="json") for o in defaults.objectives],
            operating_policy=defaults.operating_policy.model_dump(mode="json"),
        )
        self.session.add(goals)
        await self.session.flush()
        self.log.info("Business goals initialized", id=str(SINGLETON_ID))
        return goals

    async def update(
        self, data: BusinessGoalsUpdate, updated_by: UUID
    ) -> BusinessGoalsTable:
        """Apply a patch to the singleton charter. Changing goals is a logged
        decision (INTENT.md §9) — the company re-orients on direction shifts.
        """
        goals = await self.get_or_initialize()
        if data.north_star is not None:
            goals.north_star = data.north_star
        if data.constraints is not None:
            goals.constraints = list(data.constraints)
        if data.objectives is not None:
            goals.objectives = [o.model_dump(mode="json") for o in data.objectives]
        if data.operating_policy is not None:
            policy: OperatingPolicy = data.operating_policy
            goals.operating_policy = policy.model_dump(mode="json")
        await self.session.flush()
        self.log.info(
            "Business goals updated",
            id=str(SINGLETON_ID),
            updated_by=str(updated_by),
        )
        return goals


def get_business_goals_service(session: AsyncSession) -> BusinessGoalsService:
    """Get a BusinessGoalsService instance."""
    return BusinessGoalsService(session)
