"""Unit tests for the Secretary gate-classification logic.

The relay side-effect executor (3.A1) must obey the same gate list as the rest
of the company: a directive whose intent would trip a gate (spend, go_public,
new_product_line, cap_breach) is never relayed silently — it becomes a CEO
action item. ``classify_directive`` is the pure decision behind that, so it is
tested in isolation (no DB).
"""

import pytest
from roboco.models.business_goals import OperatingPolicy
from roboco.services.secretary import classify_directive, get_secretary_service
from sqlalchemy.ext.asyncio import AsyncSession

_DEFAULT_GATES = OperatingPolicy().gate_list


class TestClassifyDirective:
    def test_spend_directive_is_gated(self) -> None:
        decision = classify_directive(
            "Go ahead and purchase the premium API plan", _DEFAULT_GATES
        )
        assert decision.gated is True
        assert decision.gate == "spend"

    def test_go_public_directive_is_gated(self) -> None:
        decision = classify_directive("Make the repo public now", _DEFAULT_GATES)
        assert decision.gated is True
        assert decision.gate == "go_public"

    def test_new_product_directive_is_gated(self) -> None:
        decision = classify_directive(
            "Greenlight the analytics product pitch", _DEFAULT_GATES
        )
        assert decision.gated is True
        assert decision.gate == "new_product_line"

    def test_cap_breach_directive_is_gated(self) -> None:
        decision = classify_directive(
            "Let's exceed budget this month to move faster", _DEFAULT_GATES
        )
        assert decision.gated is True
        assert decision.gate == "cap_breach"

    def test_in_bounds_directive_passes(self) -> None:
        decision = classify_directive(
            "Tell the team to prioritize the auth refactor", _DEFAULT_GATES
        )
        assert decision.gated is False
        assert decision.gate is None

    def test_case_insensitive(self) -> None:
        decision = classify_directive("SPEND on a new domain", _DEFAULT_GATES)
        assert decision.gated is True
        assert decision.gate == "spend"

    def test_gate_removed_from_list_passes_through(self) -> None:
        # CEO loosened the leash: spend is no longer gated, so a spend
        # directive relays through ungated.
        loosened = [g for g in _DEFAULT_GATES if g != "spend"]
        decision = classify_directive("purchase a domain", loosened)
        assert decision.gated is False
        assert decision.gate is None

    def test_empty_gate_list_never_gates(self) -> None:
        decision = classify_directive("publish to the world and spend money", [])
        assert decision.gated is False


@pytest.mark.asyncio
class TestReadSurfaces:
    """DB-backed smoke: the read queries execute against the real schema.

    No data is seeded — these prove the SQL is valid and the surfaces return
    their expected shape on an empty company, which is the failure mode that
    breaks at runtime (bad column refs, enum coercion). Skipped when Postgres
    is unreachable (see conftest gating).
    """

    async def test_status_summary_shape(self, db_session: AsyncSession) -> None:
        summary = await get_secretary_service(db_session).status_summary()
        assert set(summary) >= {
            "in_flight",
            "blockers",
            "spend",
            "recent_activity",
        }
        assert "monthly_budget_usd" in summary["spend"]

    async def test_action_queue_shape(self, db_session: AsyncSession) -> None:
        queue = await get_secretary_service(db_session).action_queue()
        assert "items" in queue
        assert isinstance(queue["items"], list)
        assert queue["total"] == len(queue["items"])

    async def test_proactive_digest_shape(self, db_session: AsyncSession) -> None:
        digest = await get_secretary_service(db_session).proactive_digest()
        assert set(digest) >= {
            "pending_approvals",
            "stale_decisions",
            "fresh_pitches",
            "drift",
        }
        assert "active_objectives" in digest["drift"]
