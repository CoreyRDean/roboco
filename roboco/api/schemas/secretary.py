"""API request/response schemas for the Secretary surfaces (specs/03-secretary.md).

The read surfaces (status, queue, digest) return already-shaped dicts assembled
by ``SecretaryService``; their endpoints declare ``dict[str, Any]`` responses to
avoid duplicating the service's composition in a parallel schema. The *write*
surfaces — relay and goal-edit — carry typed request bodies and typed result
envelopes, because those are the contract the panel/agent calls against.
"""

from pydantic import BaseModel, Field

from roboco.models.business_goals import Objective, OperatingPolicy


class RelayRequest(BaseModel):
    """A CEO directive to carry downward to the Board / Main PM."""

    directive: str = Field(
        ..., min_length=1, description="The CEO's instruction, in plain language"
    )
    recipients: list[str] = Field(
        default_factory=lambda: ["main-pm"],
        min_length=1,
        description="Agent slugs to relay to (e.g. 'main-pm', 'product-owner')",
    )


class RelayResponse(BaseModel):
    """Outcome of a relay: delivered downward, or gated into a CEO action item."""

    executed: bool = Field(..., description="True if the directive was relayed")
    gated: bool = Field(
        ..., description="True if it tripped a gate and became a CEO action item"
    )
    gate: str | None = Field(
        default=None, description="Which gate it tripped, when gated"
    )
    recipients: list[str] = Field(
        default_factory=list, description="Slugs the directive was delivered to"
    )
    detail: str = Field(..., description="Human-readable explanation of the outcome")


class GoalEditRequest(BaseModel):
    """A confirmed goal edit — patch semantics, all fields optional.

    Lands in the same singleton Business Goals artifact the Panel edits.
    """

    north_star: str | None = None
    objectives: list[Objective] | None = None
    operating_policy: OperatingPolicy | None = None
    constraints: list[str] | None = None
