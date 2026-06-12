"""Business Goals domain models — the single CEO-editable company charter.

The one artifact every agent reads and the work-generation engine pursues
(INTENT.md §9). Four parts: Direction (north_star + constraints), Objectives,
Operating policy (the leash), and Derived (read-only, computed elsewhere).
Persisted as a single singleton row — see ``BusinessGoalsTable``.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from roboco.models.base import (
    AutonomyLevel,
    ObjectiveStatus,
    RobocoBase,
    StrategyCadence,
    TimestampMixin,
)

# The Business Goals artifact is a singleton; this fixed UUID is its primary key
# in the DB and the id the service fetches-or-initializes against.
SINGLETON_ID = UUID("00000000-0000-0000-0000-000000000001")


class Objective(RobocoBase):
    """One prioritized goal. Metric/target/horizon are optional — qualitative
    objectives are first-class because not everything that matters is a number.
    """

    title: str = Field(
        ..., min_length=1, max_length=200, description="Short imperative"
    )
    description: str | None = Field(default=None, description="What success looks like")
    metric: str | None = Field(default=None, description="How progress is measured")
    target: str | None = Field(default=None, description="The value that means done")
    horizon: str | None = Field(default=None, description="Timeframe, e.g. 'Q3 2026'")
    priority: int = Field(default=1, ge=1, description="Lower is higher priority")
    status: ObjectiveStatus = Field(default=ObjectiveStatus.ACTIVE)


class ProvisioningPolicy(RobocoBase):
    """Where new repos get created (INTENT.md §7 — private by default)."""

    github_org: str | None = Field(default=None)
    default_repo_visibility: str = Field(default="private")
    naming: str | None = Field(default=None)


class OperatingPolicy(RobocoBase):
    """The leash — CEO-set guardrails the strategy engine respects."""

    autonomy_level: AutonomyLevel = Field(default=AutonomyLevel.GATED)
    gate_list: list[str] = Field(
        default_factory=lambda: [
            "spend",
            "go_public",
            "new_product_line",
            "cap_breach",
        ],
        description="Actions that always require CEO approval",
    )
    monthly_budget_usd: int = Field(default=200, ge=0)
    max_active_products: int = Field(default=2, ge=0)
    strategy_cadence: StrategyCadence = Field(default=StrategyCadence.WEEKLY)
    provisioning: ProvisioningPolicy = Field(default_factory=ProvisioningPolicy)


class BusinessGoals(TimestampMixin):
    """The full CEO-editable charter — direction, objectives, operating policy."""

    id: UUID = Field(default=SINGLETON_ID, description="Singleton identifier")
    north_star: str = Field(default="", description="The company's overarching mission")
    objectives: list[Objective] = Field(default_factory=list)
    operating_policy: OperatingPolicy = Field(default_factory=OperatingPolicy)
    constraints: list[str] = Field(
        default_factory=list,
        description="Inviolable boundaries/preferences, e.g. 'no crypto'",
    )


class BusinessGoalsUpdate(RobocoBase):
    """Service-layer update DTO (all fields optional — patch semantics)."""

    north_star: str | None = None
    objectives: list[Objective] | None = None
    operating_policy: OperatingPolicy | None = None
    constraints: list[str] | None = None
