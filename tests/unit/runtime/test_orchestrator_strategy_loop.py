"""Phase 5 — the autonomous work-generation (strategy) loop ships DORMANT.

The single non-negotiable property under test: merging this phase cannot
autonomously create a task, spawn an agent, or spend anything. The loop is
double-gated — an explicit master switch (``settings.strategy_engine_enabled``,
default OFF) AND the Goals ``strategy_cadence``. While the master switch is OFF
the tick must no-op WITHOUT even opening a DB session, regardless of cadence.

These exercise the gate logic and the pure cadence/idle helpers directly on a
bare orchestrator instance (``object.__new__``), the same pattern the other
orchestrator unit tests use.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from roboco.runtime.orchestrator import AgentOrchestrator


def _bare_orchestrator() -> AgentOrchestrator:
    """An instance without the heavy __init__; init the few attrs we touch."""
    orch = object.__new__(AgentOrchestrator)
    orch._last_strategy_cycle_at = None
    orch._strategy_idle_notified = False
    return orch


# ---------------------------------------------------------------------------
# MASTER SWITCH — the dormant-by-default guarantee
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_master_disabled_no_ops_without_db() -> None:
    """Master switch OFF: the tick returns before any session is opened.

    Patches get_session_factory to explode if called — proving the disabled
    path never reads goals, never generates, never spawns.
    """
    orch = _bare_orchestrator()
    boom = patch(
        "roboco.db.base.get_session_factory",
        side_effect=AssertionError("DB touched while strategy engine disabled"),
    )
    with (
        patch("roboco.runtime.orchestrator.settings") as fake_settings,
        boom,
    ):
        fake_settings.strategy_engine_enabled = False
        # Must not raise — i.e. it returned before the get_session_factory line.
        await orch._strategy_tick()


@pytest.mark.asyncio
async def test_tick_master_disabled_even_with_weekly_cadence() -> None:
    """Cadence weekly is irrelevant while the master switch is OFF.

    Even though _strategy_cadence_elapsed would return True (no prior cycle),
    the disabled gate fires first and nothing downstream runs.
    """
    orch = _bare_orchestrator()
    with (
        patch("roboco.runtime.orchestrator.settings") as fake_settings,
        patch.object(orch, "_run_strategy_cycle", new=AsyncMock()) as run_cycle,
        patch.object(
            orch, "_strategy_caps_ok", new=AsyncMock(return_value=True)
        ) as caps,
    ):
        fake_settings.strategy_engine_enabled = False
        await orch._strategy_tick()
    run_cycle.assert_not_awaited()
    caps.assert_not_awaited()
    assert orch._last_strategy_cycle_at is None


# ---------------------------------------------------------------------------
# CADENCE — the elapsed-time gate
# ---------------------------------------------------------------------------


def test_cadence_first_cycle_always_elapsed() -> None:
    orch = _bare_orchestrator()
    assert orch._strategy_cadence_elapsed("daily") is True
    assert orch._strategy_cadence_elapsed("weekly") is True


def test_cadence_not_elapsed_within_window() -> None:
    orch = _bare_orchestrator()
    orch._last_strategy_cycle_at = datetime.now(UTC) - timedelta(hours=2)
    assert orch._strategy_cadence_elapsed("daily") is False


def test_cadence_elapsed_after_window() -> None:
    orch = _bare_orchestrator()
    orch._last_strategy_cycle_at = datetime.now(UTC) - timedelta(days=2)
    assert orch._strategy_cadence_elapsed("daily") is True


# ---------------------------------------------------------------------------
# CAPS (5.E2) — a would-be breach surfaces to the CEO and stops the cycle
# ---------------------------------------------------------------------------


class _Policy:
    def __init__(self, budget: int, max_products: int) -> None:
        self.monthly_budget_usd = budget
        self.max_active_products = max_products


@pytest.mark.asyncio
async def test_caps_budget_breach_notifies_and_blocks() -> None:
    orch = _bare_orchestrator()
    notif = AsyncMock()
    with (
        patch("roboco.services.usage.get_usage_service") as usage_factory,
        patch("roboco.services.product.get_product_service") as product_factory,
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notif,
        ),
    ):
        usage_factory.return_value.get_projection = AsyncMock(
            return_value={"projected_monthly_cost_usd": 250.0}
        )
        product_factory.return_value.list_all = AsyncMock(return_value=[])
        ok = await orch._strategy_caps_ok(db=object(), policy=_Policy(200, 2))
    assert ok is False
    notif.send_cap_breach_notification.assert_awaited_once()
    assert notif.send_cap_breach_notification.call_args.kwargs["cap"] == "budget"


@pytest.mark.asyncio
async def test_caps_product_breach_notifies_and_blocks() -> None:
    orch = _bare_orchestrator()
    notif = AsyncMock()
    with (
        patch("roboco.services.usage.get_usage_service") as usage_factory,
        patch("roboco.services.product.get_product_service") as product_factory,
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notif,
        ),
    ):
        usage_factory.return_value.get_projection = AsyncMock(
            return_value={"projected_monthly_cost_usd": 10.0}
        )
        product_factory.return_value.list_all = AsyncMock(
            return_value=[object(), object()]
        )
        ok = await orch._strategy_caps_ok(db=object(), policy=_Policy(200, 2))
    assert ok is False
    notif.send_cap_breach_notification.assert_awaited_once()
    assert notif.send_cap_breach_notification.call_args.kwargs["cap"] == "products"


@pytest.mark.asyncio
async def test_caps_ok_within_bounds() -> None:
    orch = _bare_orchestrator()
    notif = AsyncMock()
    with (
        patch("roboco.services.usage.get_usage_service") as usage_factory,
        patch("roboco.services.product.get_product_service") as product_factory,
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notif,
        ),
    ):
        usage_factory.return_value.get_projection = AsyncMock(
            return_value={"projected_monthly_cost_usd": 10.0}
        )
        product_factory.return_value.list_all = AsyncMock(return_value=[object()])
        ok = await orch._strategy_caps_ok(db=object(), policy=_Policy(200, 2))
    assert ok is True
    notif.send_cap_breach_notification.assert_not_awaited()


# ---------------------------------------------------------------------------
# HONEST IDLE (5.E3) — notify once, only when there's no real backlog
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cycle_idle_notifies_once() -> None:
    orch = _bare_orchestrator()
    notif = AsyncMock()
    with (
        patch.object(orch, "_strategy_generate", new=AsyncMock(return_value=0)),
        patch.object(
            orch, "_strategy_has_real_backlog", new=AsyncMock(return_value=False)
        ),
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notif,
        ),
    ):
        await orch._run_strategy_cycle(db=object(), goals=object(), policy=object())
        await orch._run_strategy_cycle(db=object(), goals=object(), policy=object())
    notif.send_need_direction_notification.assert_awaited_once()
    assert orch._strategy_idle_notified is True


@pytest.mark.asyncio
async def test_cycle_no_idle_when_backlog_remains() -> None:
    """No generation but live backlog => not idle, no CEO ping (false-idle guard)."""
    orch = _bare_orchestrator()
    notif = AsyncMock()
    with (
        patch.object(orch, "_strategy_generate", new=AsyncMock(return_value=0)),
        patch.object(
            orch, "_strategy_has_real_backlog", new=AsyncMock(return_value=True)
        ),
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notif,
        ),
    ):
        await orch._run_strategy_cycle(db=object(), goals=object(), policy=object())
    notif.send_need_direction_notification.assert_not_awaited()
    assert orch._strategy_idle_notified is False


@pytest.mark.asyncio
async def test_cycle_generation_rearms_idle_signal() -> None:
    orch = _bare_orchestrator()
    orch._strategy_idle_notified = True  # previously idle
    with patch.object(orch, "_strategy_generate", new=AsyncMock(return_value=3)):
        await orch._run_strategy_cycle(db=object(), goals=object(), policy=object())
    assert orch._strategy_idle_notified is False


# ---------------------------------------------------------------------------
# Track D placeholder — generates nothing (safe no-op)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TRACK D — decision logic (5.D1) + routing (5.D2)
#
# Bounded, deterministic heuristics: at most ONE item per cycle, routed by the
# autonomy line. New-product work goes through the GATED pitch path; in-bounds
# work goes straight to delivery; propose_only surfaces instead of running.
# All paths are exercised offline by patching the service factories.
# ---------------------------------------------------------------------------


class _Objective:
    """Plain stand-in for a validated business Objective."""

    def __init__(  # noqa: PLR0913 — test stand-in mirrors the Objective fields
        self,
        title: str,
        priority: int = 1,
        status: str = "active",
        description: str | None = None,
        metric: str | None = None,
        target: str | None = None,
    ) -> None:
        self.title = title
        self.priority = priority
        self.status = type("S", (), {"value": status})()
        self.description = description
        self.metric = metric
        self.target = target


class _Goals:
    def __init__(self, objectives: list[Any]) -> None:
        # _strategy_generate calls Objective.model_validate on each; we patch
        # that to passthrough so these stand-ins flow through unchanged.
        self.objectives = objectives


class _GenPolicy:
    def __init__(self, autonomy: str = "gated") -> None:
        self.autonomy_level = autonomy
        self.gate_list = ["new_product_line", "spend", "go_public", "cap_breach"]


def _patch_validate() -> Any:
    """Make Objective.model_validate a passthrough for the stand-ins."""
    return patch(
        "roboco.models.business_goals.Objective.model_validate",
        side_effect=lambda o: o,
    )


@pytest.mark.asyncio
async def test_generate_no_active_objectives_is_noop() -> None:
    """No active objective -> nothing to originate (honest idle handles it)."""
    orch = _bare_orchestrator()
    goals = _Goals([_Objective("done", status="achieved")])
    with _patch_validate():
        generated = await orch._strategy_generate(
            db=object(), goals=goals, policy=_GenPolicy()
        )
    assert generated == 0


@pytest.mark.asyncio
async def test_generate_skips_when_work_already_in_flight() -> None:
    """If the delivery engine is already busy, originate nothing this cycle."""
    orch = _bare_orchestrator()
    goals = _Goals([_Objective("grow", priority=1)])
    drift = AsyncMock(return_value={"in_flight_tasks": 3, "active_objectives": 1})
    with (
        _patch_validate(),
        patch("roboco.services.secretary.get_secretary_service") as sec_factory,
    ):
        sec_factory.return_value._drift_signals = drift
        generated = await orch._strategy_generate(
            db=object(), goals=goals, policy=_GenPolicy()
        )
    assert generated == 0


@pytest.mark.asyncio
async def test_generate_no_product_routes_new_product_pitch_gated() -> None:
    """No product line yet -> route the top objective through the GATED pitch."""
    orch = _bare_orchestrator()
    goals = _Goals(
        [
            _Objective("ship the flagship", priority=1, description="a thing"),
            _Objective("secondary", priority=2),
        ]
    )
    create_pitch = AsyncMock(return_value=type("T", (), {"id": "x", "status": "p"})())
    with (
        _patch_validate(),
        patch("roboco.services.secretary.get_secretary_service") as sec_factory,
        patch("roboco.services.product.get_product_service") as prod_factory,
        patch("roboco.services.task.TaskService") as task_cls,
    ):
        sec_factory.return_value._drift_signals = AsyncMock(
            return_value={"in_flight_tasks": 0, "active_objectives": 2}
        )
        # No products -> new-product path.
        prod_factory.return_value.list_all = AsyncMock(return_value=[])
        task_cls.return_value.create_pitch = create_pitch
        task_cls.return_value.create = AsyncMock()
        generated = await orch._strategy_generate(
            db=object(), goals=goals, policy=_GenPolicy()
        )
    assert generated == 1
    # Routed through the GATED pitch path, NOT straight to delivery.
    create_pitch.assert_awaited_once()
    task_cls.return_value.create.assert_not_awaited()
    # Highest-priority objective was the one selected.
    req = create_pitch.call_args.args[0]
    assert req.objective == "ship the flagship"


@pytest.mark.asyncio
async def test_generate_with_product_routes_in_bounds_delivery() -> None:
    """A product exists -> originate in-bounds delivery work (not a pitch)."""
    orch = _bare_orchestrator()
    goals = _Goals([_Objective("harden the product", priority=1)])
    create = AsyncMock()
    create_pitch = AsyncMock()
    with (
        _patch_validate(),
        patch("roboco.services.secretary.get_secretary_service") as sec_factory,
        patch("roboco.services.product.get_product_service") as prod_factory,
        patch("roboco.services.project.get_project_service") as proj_factory,
        patch("roboco.services.task.TaskService") as task_cls,
    ):
        sec_factory.return_value._drift_signals = AsyncMock(
            return_value={"in_flight_tasks": 0, "active_objectives": 1}
        )
        product = type("P", (), {"id": "prod-1"})()
        prod_factory.return_value.list_all = AsyncMock(return_value=[product])
        prod_factory.return_value.project_for = AsyncMock(return_value="proj-1")
        proj_factory.return_value.list_all = AsyncMock(return_value=[])
        task_cls.return_value.create = create
        task_cls.return_value.create_pitch = create_pitch
        generated = await orch._strategy_generate(
            db=object(), goals=goals, policy=_GenPolicy()
        )
    assert generated == 1
    create.assert_awaited_once()
    create_pitch.assert_not_awaited()
    req = create.call_args.args[0]
    assert req.project_id == "proj-1"
    assert req.source == "strategy_engine"


@pytest.mark.asyncio
async def test_generate_propose_only_surfaces_instead_of_running() -> None:
    """propose_only autonomy: surface the in-bounds work, run nothing."""
    orch = _bare_orchestrator()
    goals = _Goals([_Objective("iterate", priority=1)])
    notif = AsyncMock()
    create = AsyncMock()
    with (
        _patch_validate(),
        patch("roboco.services.secretary.get_secretary_service") as sec_factory,
        patch("roboco.services.product.get_product_service") as prod_factory,
        patch("roboco.services.task.TaskService") as task_cls,
        patch("roboco.services.notification.NotificationService", return_value=notif),
    ):
        sec_factory.return_value._drift_signals = AsyncMock(
            return_value={"in_flight_tasks": 0, "active_objectives": 1}
        )
        prod_factory.return_value.list_all = AsyncMock(
            return_value=[type("P", (), {"id": "prod-1"})()]
        )
        task_cls.return_value.create = create
        generated = await orch._strategy_generate(
            db=object(), goals=goals, policy=_GenPolicy(autonomy="propose_only")
        )
    assert generated == 0
    create.assert_not_awaited()
    notif.send_need_direction_notification.assert_awaited_once()
