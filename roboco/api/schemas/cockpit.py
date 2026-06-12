"""API response schema for the CEO cockpit derived-state summary (Phase 6).

The cockpit summary (``GET /api/cockpit/summary``, 6.B1) is *derived* state
composed from existing services — Business Goals, the Secretary's drift signal,
``UsageService`` spend projection, and the ``ProductService`` active-product
count. It answers the cockpit's "Is the business winning?" question.

Honest-boundary note (spec §"On winning"): every performance number here is a
**proxy** until real external launches are greenlit. The ``basis`` field on the
summary makes that explicit on the wire so the panel can label it on screen and
never pretend to measure revenue that isn't there.
"""

from pydantic import BaseModel, Field


class ObjectiveProgress(BaseModel):
    """One active objective with its proxy coverage signal.

    There is no objective->task linkage in the data model today, so progress is
    not a stored percentage — it is the honest coverage proxy the work engine
    itself uses: whether any work is in flight behind the standing objectives.
    """

    title: str = Field(..., description="The objective's short imperative")
    priority: int = Field(..., description="Lower is higher priority")
    metric: str | None = Field(default=None, description="How progress is measured")
    target: str | None = Field(default=None, description="The value that means done")
    horizon: str | None = Field(default=None, description="Timeframe, e.g. 'Q3 2026'")
    has_work_behind_it: bool = Field(
        ...,
        description=(
            "Proxy coverage: True when work is in flight that can serve the "
            "objectives. Company-wide today (no per-objective task linkage)."
        ),
    )


class GoalCoverage(BaseModel):
    """Are the active objectives covered by work, and is work tied to a goal?"""

    active_objectives: int = Field(..., description="Count of active objectives")
    in_flight_tasks: int = Field(..., description="Count of in-flight tasks")
    work_without_objectives: bool = Field(
        ..., description="Work is happening with no active objective behind it"
    )
    objectives_without_work: bool = Field(
        ..., description="Objectives are set but no work is in flight"
    )


class SpendVsBudget(BaseModel):
    """Projected monthly spend against the operating-policy budget cap."""

    monthly_budget_usd: int = Field(..., description="The CEO-set monthly cap")
    spend_30d_usd: float = Field(..., description="Actual cost over the last 30 days")
    projected_monthly_usd: float = Field(
        ..., description="7-day-rolling projection of monthly cost"
    )
    projected_pct_of_budget: float | None = Field(
        default=None, description="Projection as a percent of the cap (None if cap=0)"
    )
    over_budget: bool = Field(..., description="Projection exceeds the cap")


class ActiveProductsVsCap(BaseModel):
    """Registered (active) products against the operating-policy concurrency cap.

    Products are not status-scoped today, so every registered product counts as
    active — the same rule the strategy-cap gate enforces (orchestrator
    ``_strategy_caps_ok``), so this matches what halts a generation cycle.
    """

    active_products: int = Field(..., description="Count of registered products")
    max_active_products: int = Field(..., description="The CEO-set concurrency cap")
    at_cap: bool = Field(..., description="Active count has reached or passed the cap")


class CockpitSummaryResponse(BaseModel):
    """Derived cockpit state — 'Is the business winning?' at a glance.

    Composed read-only from existing services; no new measurement machinery.
    ``basis`` is ``"proxy"`` until real external launches are greenlit (spec
    §"On winning") — the cockpit shows proxy outcomes by design.
    """

    basis: str = Field(
        default="proxy",
        description=(
            "Honest-boundary label. 'proxy' until real external launches are "
            "greenlit; the cockpit does not pretend to measure revenue."
        ),
    )
    objectives: list[ObjectiveProgress] = Field(
        default_factory=list, description="Per-objective proxy progress"
    )
    goal_coverage: GoalCoverage = Field(..., description="Coverage + drift signal")
    spend: SpendVsBudget = Field(..., description="Spend vs budget cap")
    products: ActiveProductsVsCap = Field(..., description="Active products vs cap")
    generated_at: str = Field(..., description="ISO-8601 timestamp of this snapshot")
