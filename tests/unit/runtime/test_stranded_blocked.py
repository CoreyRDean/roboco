"""Stall surfacing (Phase 5, 5.A1): stranded ``blocked`` tasks reach the CEO.

Background
----------
The existing stall detectors cover agents that are *running but not
advancing* (``_pm_respawn_should_gate``) and per-role SLA drift
(``_detect_sla_exceeded``). Neither covers a task parked in ``blocked``
with no automatic path forward — a HITL block, an auto-block from a
failed step (the merge-405 / PR-base-422 we hit), a hard error, or a
stuck state. ``_dispatch_blocker_work`` deliberately skips HITL blocks,
so such a task can sit indefinitely while the company looks idle.

``_detect_stranded_blocked`` closes that gap (INTENT.md §10): it surfaces
each stranded task to the CEO action queue exactly ONCE per stall episode
and re-arms once the task recovers out of ``blocked``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from roboco.runtime.orchestrator import AgentOrchestrator


def _new_orchestrator() -> AgentOrchestrator:
    """Bypass __init__ so tests don't need a full DI graph."""
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    cast("Any", orch)._stranded_blocked_notified = set()
    return orch


def _aged_iso(minutes: int) -> str:
    """ISO timestamp ``minutes`` in the past (drives ``_time_in_state``)."""
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def _hitl_task(task_id: str, *, age_minutes: int) -> dict[str, Any]:
    return {
        "id": task_id,
        "status": "blocked",
        "blocker_resolver_type": "human",
        "updated_at": _aged_iso(age_minutes),
    }


@pytest.mark.asyncio
async def test_hitl_blocked_task_surfaces_to_ceo_once() -> None:
    """A HITL-blocked task past the grace window reaches the CEO exactly once."""
    orch = _new_orchestrator()
    task_id = str(uuid4())
    task = _hitl_task(task_id, age_minutes=10)

    notifier = AsyncMock()
    notifier.send_stranded_task_notification = AsyncMock()

    with (
        patch.object(orch, "_fetch_tasks", AsyncMock(return_value=[task])),
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notifier,
        ),
    ):
        # First sweep surfaces it.
        await orch._detect_stranded_blocked(AsyncMock())
        # Second sweep (same still-blocked task) must NOT re-notify.
        await orch._detect_stranded_blocked(AsyncMock())

    notifier.send_stranded_task_notification.assert_awaited_once()
    kwargs = notifier.send_stranded_task_notification.await_args.kwargs
    assert kwargs["task_id"] == task_id
    assert kwargs["to_ceo"] == "ceo"
    assert task_id in orch._stranded_blocked_notified


@pytest.mark.asyncio
async def test_hitl_block_within_grace_is_not_surfaced() -> None:
    """A just-blocked HITL task is given grace — not reported as stranded yet."""
    orch = _new_orchestrator()
    task = _hitl_task(str(uuid4()), age_minutes=1)

    notifier = AsyncMock()
    notifier.send_stranded_task_notification = AsyncMock()

    with (
        patch.object(orch, "_fetch_tasks", AsyncMock(return_value=[task])),
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notifier,
        ),
    ):
        await orch._detect_stranded_blocked(AsyncMock())

    notifier.send_stranded_task_notification.assert_not_awaited()
    assert orch._stranded_blocked_notified == set()


@pytest.mark.asyncio
async def test_blocked_with_resolver_within_window_not_stranded() -> None:
    """A non-HITL block with a resolver, still fresh, is NOT stranded.

    ``_dispatch_blocker_work`` is actively working it (a cell PM can be
    dispatched), so it must not be surfaced before the stale threshold.
    """
    orch = _new_orchestrator()
    task = {
        "id": str(uuid4()),
        "status": "blocked",
        "team": "backend",
        "updated_at": _aged_iso(5),
    }

    notifier = AsyncMock()
    notifier.send_stranded_task_notification = AsyncMock()

    with (
        patch.object(orch, "_fetch_tasks", AsyncMock(return_value=[task])),
        patch.object(orch, "_blocker_resolver_slug", return_value="be-pm"),
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notifier,
        ),
    ):
        await orch._detect_stranded_blocked(AsyncMock())

    notifier.send_stranded_task_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_block_with_resolver_surfaces() -> None:
    """A block that has sat far past the resolver window IS stranded.

    A failed step / hard error leaves the task blocked while the resolver
    never moves it; after the stale threshold the CEO must hear about it.
    """
    orch = _new_orchestrator()
    task = {
        "id": str(uuid4()),
        "status": "blocked",
        "team": "backend",
        "updated_at": _aged_iso(45),  # past _STRANDED_BLOCKED_SECONDS (30m)
    }

    notifier = AsyncMock()
    notifier.send_stranded_task_notification = AsyncMock()

    with (
        patch.object(orch, "_fetch_tasks", AsyncMock(return_value=[task])),
        patch.object(orch, "_blocker_resolver_slug", return_value="be-pm"),
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notifier,
        ),
    ):
        await orch._detect_stranded_blocked(AsyncMock())

    notifier.send_stranded_task_notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_blocked_with_no_resolver_surfaces_after_grace() -> None:
    """A block with no dispatchable resolver is stranded once aged."""
    orch = _new_orchestrator()
    task = {
        "id": str(uuid4()),
        "status": "blocked",
        "updated_at": _aged_iso(10),
    }

    notifier = AsyncMock()
    notifier.send_stranded_task_notification = AsyncMock()

    with (
        patch.object(orch, "_fetch_tasks", AsyncMock(return_value=[task])),
        patch.object(orch, "_blocker_resolver_slug", return_value=None),
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notifier,
        ),
    ):
        await orch._detect_stranded_blocked(AsyncMock())

    notifier.send_stranded_task_notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_recovery_rearms_the_signal() -> None:
    """Once a task leaves ``blocked``, a future stall notifies again.

    The in-memory one-shot set must drop a task that is no longer in the
    blocked fetch, so a fresh stall on the same id re-fires the signal.
    """
    orch = _new_orchestrator()
    task_id = str(uuid4())
    task = _hitl_task(task_id, age_minutes=10)

    notifier = AsyncMock()
    notifier.send_stranded_task_notification = AsyncMock()

    with patch(
        "roboco.services.notification.NotificationService",
        return_value=notifier,
    ):
        # Episode 1: stranded -> notified.
        with patch.object(orch, "_fetch_tasks", AsyncMock(return_value=[task])):
            await orch._detect_stranded_blocked(AsyncMock())
        assert task_id in orch._stranded_blocked_notified

        # Recovered: no longer in the blocked set -> dropped from the guard.
        with patch.object(orch, "_fetch_tasks", AsyncMock(return_value=[])):
            await orch._detect_stranded_blocked(AsyncMock())
        assert orch._stranded_blocked_notified == set()

        # Episode 2: stalls again -> notifies anew.
        with patch.object(orch, "_fetch_tasks", AsyncMock(return_value=[task])):
            await orch._detect_stranded_blocked(AsyncMock())

    expected_notifications = 2  # one per stall episode
    assert (
        notifier.send_stranded_task_notification.await_count == expected_notifications
    )


@pytest.mark.asyncio
async def test_notification_failure_does_not_crash_sweep() -> None:
    """A notification error is swallowed — the dispatcher must not wedge."""
    orch = _new_orchestrator()
    task = _hitl_task(str(uuid4()), age_minutes=10)

    notifier = AsyncMock()
    notifier.send_stranded_task_notification = AsyncMock(
        side_effect=RuntimeError("delivery down")
    )

    with (
        patch.object(orch, "_fetch_tasks", AsyncMock(return_value=[task])),
        patch(
            "roboco.services.notification.NotificationService",
            return_value=notifier,
        ),
    ):
        # Must not raise.
        await orch._detect_stranded_blocked(AsyncMock())

    notifier.send_stranded_task_notification.assert_awaited_once()
