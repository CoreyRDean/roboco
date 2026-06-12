"""A Board pitch surfaces to the CEO Approve & Start gate (Phase 4 — 4.E1).

A pitch (``source='pitch'``) is authored already board-reviewed
(``board_review_complete=True``, still ``pending``, ``team=board``), so it is
queue-ready the moment it exists and must NOT be re-reviewed by the board or
routed to a PM. The orchestrator emits exactly ONE formal CEO notification per
pitch and then leaves it pending for the CEO's decision.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from roboco.runtime.orchestrator import AgentOrchestrator


def _make_orch() -> AgentOrchestrator:
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch._instances = {}
    orch._pitch_ceo_notified = set()
    return orch


def _pitch_task(**overrides: Any) -> dict[str, Any]:
    task: dict[str, Any] = {
        "id": str(uuid4()),
        "status": "pending",
        "team": "board",
        "title": "A calm workbench for solo AI devs",
        "description": "A board-authored product proposal.",
        "assigned_to": None,
        "board_review_complete": True,
        "source": "pitch",
    }
    task.update(overrides)
    return task


@pytest.mark.asyncio
async def test_pitch_surfaces_to_ceo_once_and_halts_dispatch() -> None:
    orch = _make_orch()
    task = _pitch_task()
    notif = AsyncMock()
    with patch(
        "roboco.services.notification.NotificationService",
        return_value=notif,
    ):
        handled = await orch._maybe_surface_pitch_to_ceo(task)
    assert handled is True
    notif.send_pitch_ready_notification.assert_awaited_once()
    _, kwargs = notif.send_pitch_ready_notification.call_args
    assert kwargs["task_id"] == task["id"]

    # Second pass: already notified — still halts dispatch, no second notify.
    notif2 = AsyncMock()
    with patch(
        "roboco.services.notification.NotificationService",
        return_value=notif2,
    ):
        handled_again = await orch._maybe_surface_pitch_to_ceo(task)
    assert handled_again is True
    notif2.send_pitch_ready_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_pitch_task_is_not_intercepted() -> None:
    orch = _make_orch()
    task = _pitch_task(source="manual")
    handled = await orch._maybe_surface_pitch_to_ceo(task)
    assert handled is False


@pytest.mark.asyncio
async def test_approved_pitch_handed_to_main_pm_is_not_re_surfaced() -> None:
    """Once approve_and_start re-targets the pitch to Main PM (team→main_pm),
    it is normal PM work and the surfacing interceptor must let it pass."""
    orch = _make_orch()
    task = _pitch_task(team="main_pm")
    handled = await orch._maybe_surface_pitch_to_ceo(task)
    assert handled is False


@pytest.mark.asyncio
async def test_surface_failure_clears_guard_for_retry() -> None:
    orch = _make_orch()
    task = _pitch_task()
    notif = AsyncMock()
    notif.send_pitch_ready_notification.side_effect = RuntimeError("boom")
    with patch(
        "roboco.services.notification.NotificationService",
        return_value=notif,
    ):
        handled = await orch._maybe_surface_pitch_to_ceo(task)
    # Still halts dispatch (it IS a pitch), but the guard is cleared so a later
    # tick retries rather than the signal being lost forever.
    assert handled is True
    assert task["id"] not in orch._pitch_ceo_notified
