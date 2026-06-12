"""Pitch-provisioning reads the structured contract Track D actually writes.

``TaskService.create_pitch`` persists the pitch content under
``proactive_context['pitch']`` (objective / the_work / name …). The
provisioning service must read it from there — and derive the participating
cells from the per-cell ``the_work`` slices — so a multi-cell pitch fans out to
one repo per cell while a thin pitch stays a single repo. (Phase 4 — 4.E2 join.)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from roboco.models.base import Team
from roboco.services.pitch_provisioning import PitchProvisioningService


def _svc() -> PitchProvisioningService:
    return PitchProvisioningService(MagicMock())


def _task(*, proactive_context: Any = None, plan: Any = None) -> MagicMock:
    task = MagicMock()
    task.proactive_context = proactive_context
    task.plan = plan
    return task


def test_pitch_meta_read_from_proactive_context() -> None:
    task = _task(proactive_context={"pitch": {"name": "Acme", "objective": "calm"}})
    meta = _svc()._pitch_meta(task)
    assert meta["name"] == "Acme"
    assert meta["objective"] == "calm"


def test_pitch_meta_falls_back_to_plan() -> None:
    """An older/thin pitch that stashed content on the plan still reads."""
    task = _task(proactive_context=None, plan={"pitch": {"name": "Legacy"}})
    assert _svc()._pitch_meta(task)["name"] == "Legacy"


def test_multi_cell_derived_from_the_work() -> None:
    task = _task(
        proactive_context={
            "pitch": {
                "name": "Acme",
                "the_work": [
                    {"team": "backend", "summary": "api"},
                    {"team": "frontend", "summary": "ui"},
                ],
            }
        }
    )
    assert _svc()._pitch_cells(task) == [Team.BACKEND, Team.FRONTEND]


def test_explicit_cells_take_priority_over_the_work() -> None:
    task = _task(
        proactive_context={
            "pitch": {
                "cells": ["backend"],
                "the_work": [{"team": "frontend"}],
            }
        }
    )
    assert _svc()._pitch_cells(task) == [Team.BACKEND]


def test_thin_pitch_is_single_repo() -> None:
    """No cells and no the_work → single-repo product (empty cell list)."""
    task = _task(proactive_context={"pitch": {"name": "Solo Tool"}})
    assert _svc()._pitch_cells(task) == []
