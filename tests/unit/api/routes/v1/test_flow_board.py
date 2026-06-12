"""Unit tests for /api/v1/flow/board/* endpoints.

Uses a minimal FastAPI test client built from the new router only.
No DB required — Choreographer is mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from roboco.api.deps import get_choreographer
from roboco.api.routes.v1.flow_board import router

_HTTP_200 = 200
_HTTP_422 = 422

_AGENT_ID = str(uuid4())
_TASK_ID = str(uuid4())
_HEADERS = {"X-Agent-ID": _AGENT_ID, "X-Agent-Role": "product_owner"}


def _make_envelope(
    status: str = "ok", task_id: str | None = None, **extra: object
) -> MagicMock:
    """Return a mock Envelope whose as_dict() returns a predictable payload."""
    env = MagicMock()
    payload: dict[str, object] = {"status": status, "task_id": task_id, "next": "..."}
    payload.update(extra)
    env.as_dict.return_value = payload
    return env


def _build_app(mock_choreographer: MagicMock) -> FastAPI:
    """Build minimal FastAPI app with the flow_board router and a mocked dep."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_choreographer] = lambda: mock_choreographer
    return app


@pytest.mark.asyncio
async def test_triage_returns_envelope() -> None:
    """POST /api/v1/flow/board/triage returns 200 with envelope shape."""
    mock_chore = MagicMock()
    mock_chore.board_triage = AsyncMock(
        return_value=_make_envelope(status="awaiting_pm_review", task_id=_TASK_ID)
    )
    client = TestClient(_build_app(mock_chore))

    resp = client.post(
        "/api/v1/flow/board/triage",
        json={},
        headers=_HEADERS,
    )

    assert resp.status_code == _HTTP_200
    body = resp.json()
    assert body["status"] == "awaiting_pm_review"
    mock_chore.board_triage.assert_awaited_once()


@pytest.mark.asyncio
async def test_escalate_to_ceo_returns_envelope() -> None:
    """POST /api/v1/flow/board/escalate_to_ceo forwards task_id and reason."""
    mock_chore = MagicMock()
    mock_chore.escalate_to_ceo = AsyncMock(
        return_value=_make_envelope(status="awaiting_ceo_approval", task_id=_TASK_ID)
    )
    client = TestClient(_build_app(mock_chore))

    resp = client.post(
        "/api/v1/flow/board/escalate_to_ceo",
        json={"task_id": _TASK_ID, "reason": "Strategic call needs CEO sign-off."},
        headers=_HEADERS,
    )

    assert resp.status_code == _HTTP_200
    body = resp.json()
    assert body["status"] == "awaiting_ceo_approval"
    mock_chore.escalate_to_ceo.assert_awaited_once()
    call_args = mock_chore.escalate_to_ceo.call_args
    assert str(call_args.args[1]) == _TASK_ID
    assert call_args.args[2] == "Strategic call needs CEO sign-off."


def test_escalate_to_ceo_validates_reason_required() -> None:
    """POST escalate_to_ceo rejects empty reason (min_length=1)."""
    mock_chore = MagicMock()
    client = TestClient(_build_app(mock_chore))

    resp = client.post(
        "/api/v1/flow/board/escalate_to_ceo",
        json={"task_id": _TASK_ID, "reason": ""},
        headers=_HEADERS,
    )

    assert resp.status_code == _HTTP_422


_VALID_PITCH_BODY: dict[str, object] = {
    "title": "Solo Dev Workbench",
    "objective": "One calm workbench for solo AI developers; serves the v1 goal.",
    "what_this_builds": ["A web app", "A CLI"],
    "the_work": [
        {"team": "backend", "summary": "API + storage", "items": ["endpoints"]},
        {"team": "frontend", "summary": "the UI", "items": ["panels"]},
    ],
    "success_criteria": ["A solo dev ships a project end to end in under an hour"],
    "rationale": "Research shows solo AI devs juggle five disconnected tools.",
    "notes": ["Reuse the existing auth module"],
}


@pytest.mark.asyncio
async def test_pitch_returns_envelope_and_forwards_contract() -> None:
    """POST /api/v1/flow/board/pitch maps the body onto PitchInputs."""
    mock_chore = MagicMock()
    mock_chore.pitch = AsyncMock(
        return_value=_make_envelope(status="pending", task_id=_TASK_ID)
    )
    client = TestClient(_build_app(mock_chore))

    resp = client.post(
        "/api/v1/flow/board/pitch",
        json=_VALID_PITCH_BODY,
        headers=_HEADERS,
    )

    assert resp.status_code == _HTTP_200
    body = resp.json()
    assert body["status"] == "pending"
    mock_chore.pitch.assert_awaited_once()
    inputs = mock_chore.pitch.call_args.args[1]
    assert inputs.title == "Solo Dev Workbench"
    assert inputs.the_work[0]["team"] == "backend"
    assert inputs.success_criteria


def test_pitch_validates_required_fields() -> None:
    """POST pitch rejects an empty the_work / success_criteria (min_length=1)."""
    mock_chore = MagicMock()
    client = TestClient(_build_app(mock_chore))

    bad = {**_VALID_PITCH_BODY, "the_work": [], "success_criteria": []}
    resp = client.post("/api/v1/flow/board/pitch", json=bad, headers=_HEADERS)

    assert resp.status_code == _HTTP_422


@pytest.mark.asyncio
async def test_i_am_idle_returns_envelope() -> None:
    """POST /api/v1/flow/board/i_am_idle delegates to Choreographer.i_am_idle."""
    mock_chore = MagicMock()
    mock_chore.i_am_idle = AsyncMock(return_value=_make_envelope(status="idle"))
    client = TestClient(_build_app(mock_chore))

    resp = client.post(
        "/api/v1/flow/board/i_am_idle",
        json={},
        headers=_HEADERS,
    )

    assert resp.status_code == _HTTP_200
    body = resp.json()
    assert body["status"] == "idle"
    mock_chore.i_am_idle.assert_awaited_once()
