"""Board + Auditor verbs (first per-role split).

Mixin extracted from ``_impl.py`` to prove the per-role pattern. Relies
on ``self.task`` and ``self._briefing_for`` from the base class via
Python's MRO. ``board_triage`` and ``auditor_triage`` are read-only
verbs that don't share helper code with any other role, making this
the safest first extraction.

``pitch`` (Phase 4) is the Board's product-origination verb. Like
``board_triage`` it is a "special" verb — it ORIGINATES a new root task
rather than transitioning an existing one, so ``IntentSpec.composes`` is
empty and the verb body owns the creation dispatch
(``TaskService.create_pitch``). The spec gate still runs first and
enforces role membership (Product Owner + Head of Marketing only); the
pitch task does not exist yet, so the gate is called with ``task=None``
(safe for an empty-composes verb — only ``allowed_roles`` +
extra-preconditions are evaluated, and ``pitch`` declares none).

The mixin inherits from ``ChoreographerHelpers`` only when type-checking
so mypy resolves ``self.task`` etc. to the typed surface. At runtime
the actual class is composed in ``__init__.py`` and inherits from
``_LegacyChoreographer`` (where the real implementations live).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from roboco.foundation.policy import lifecycle as spec_module
from roboco.services.gateway.envelope import Envelope

if TYPE_CHECKING:
    from uuid import UUID

    from roboco.services.gateway.choreographer._protocol import ChoreographerHelpers

    _Base = ChoreographerHelpers
else:
    _Base = object


@dataclass(frozen=True)
class PitchInputs:
    """The well-formed-pitch content contract the ``pitch`` verb receives.

    Mirrors the intake draft shape
    (``roboco.api.schemas.prompter.PrompterDraftTask`` / ``compose_description``)
    as its structural model so a pitch and an intake draft render through the
    SAME deterministic prose composition. A pitch is "a credible bet, not a
    thought" — the fields capture what it is, the objective it serves, what it
    builds, the per-cell work, success criteria, and the rationale grounded in
    research.

    Frozen so the helper sites can't mutate caller state.
    """

    # name — the pitch's title.
    title: str
    # The outcome / objective this product serves (one or two sentences). The
    # Board grounds this in the company goals + research.
    objective: str
    # Concrete artifacts the product would ship.
    what_this_builds: list[str]
    # Per-cell breakdown: list of {team, summary, items} (the CellWork shape).
    # Length drives single-cell vs multi-cell (board-led) provisioning.
    the_work: list[dict[str, Any]]
    # The pitch's success criteria — what "this worked" looks like.
    success_criteria: list[str]
    # Why now — the rationale, grounded in research (a credible bet).
    rationale: str
    # Constraints, reuse pointers, things to confirm with the CEO.
    notes: list[str] = field(default_factory=list)
    priority: int = 2


class BoardMixin(_Base):
    """Board (Product Owner + Head Marketing) + Auditor verbs."""

    async def pitch(self, board_agent_id: UUID, inputs: PitchInputs) -> Envelope:
        """Phase 4: Board authors a new product PITCH → CEO Approve & Start queue.

        The verb originates a ROOT proposal task in the exact state the CEO
        queue surfaces (pending + board_review_complete + team=board) so the
        CEO can approve, reject, or keep discussing. Greenlighting a new product
        line is gated, so the pitch always reaches the human; on approval the
        provisioning path autonomously creates the private repo(s), registers
        the project/product, and seeds delivery.

        Spec gate runs first (role membership: Product Owner + Head of Marketing
        only). The pitch task does not exist yet, so the gate is called with
        ``task=None`` — safe because ``pitch`` composes no atomic action and
        declares no extra preconditions, so only ``allowed_roles`` is evaluated.
        After the gate accepts, the verb body composes a human-readable
        description from the structured contract (reusing the intake
        ``compose_description``) and dispatches ``TaskService.create_pitch``.
        """
        from roboco.models.task import PitchCreateRequest
        from roboco.services.prompter import compose_description

        agent = await self.task.agent_for(board_agent_id)
        role_str = str(agent.role) if agent is not None else "product_owner"
        briefing = await self._briefing_for(board_agent_id, None)
        try:
            role = spec_module.Role(role_str)
        except ValueError:
            return await self._emit_rejection(
                Envelope.not_authorized(
                    message=f"unknown role '{role_str}'",
                    remediate="role is not declared in the lifecycle spec",
                    context_briefing=briefing,
                ),
                agent_id=board_agent_id,
                task_id=None,
                verb="pitch",
            )
        decision = spec_module.can_invoke_intent(role, "pitch", None, None)
        if not decision.allowed:
            return await self._emit_rejection(
                Envelope.from_decision(decision, briefing=briefing),
                agent_id=board_agent_id,
                task_id=None,
                verb="pitch",
            )

        # Compose the human-readable description from the structured contract,
        # exactly as intake composes a draft: the CEO reads prose in the queue,
        # while the structured fields are also persisted verbatim for provisioning.
        description = compose_description(
            {
                "objective": inputs.objective,
                "what_this_builds": inputs.what_this_builds,
                "the_work": inputs.the_work,
                # Surface the rationale (why now) inside Notes so it renders in
                # the queue card alongside the author's other notes.
                "notes": [*inputs.notes, f"Rationale: {inputs.rationale}"],
                "acceptance_criteria": inputs.success_criteria,
                "description": inputs.objective,  # fallback if structure is sparse
            }
        )
        new_task = await self.task.create_pitch(
            PitchCreateRequest(
                title=inputs.title,
                description=description,
                acceptance_criteria=inputs.success_criteria,
                created_by=board_agent_id,
                objective=inputs.objective,
                what_this_builds=list(inputs.what_this_builds),
                the_work=list(inputs.the_work),
                notes=list(inputs.notes),
                rationale=inputs.rationale,
                priority=inputs.priority,
            )
        )
        return Envelope.ok(
            status=str(new_task.status),
            task_id=str(new_task.id),
            next=spec_module._INTENT_VERBS["pitch"].next_hint(new_task),
            context_briefing=await self._briefing_for(board_agent_id, new_task.id),
        )

    async def board_triage(self, board_agent_id: UUID) -> Envelope:
        """Phase 4: Board triage — next strategic root task awaiting PM review."""
        strategic = await self.task.list_strategic_for_board()
        if strategic:
            t = strategic[0]
            return Envelope.ok(
                status=str(t.status),
                task_id=str(t.id),
                next=(
                    f"review and call escalate_to_ceo(task_id='{t.id}', reason=...)"
                    " or i_am_idle"
                ),
                context_briefing=await self._briefing_for(board_agent_id, t.id),
            )
        return Envelope.ok(
            status="idle",
            task_id=None,
            next="no strategic-review work — i_am_idle",
            context_briefing=await self._briefing_for(board_agent_id, None),
        )

    async def auditor_triage(self, auditor_agent_id: UUID) -> Envelope:
        """Phase 4: Auditor triage — surfaces anomalies (long-running blocked, etc.)."""
        anomalies = await self.task.list_long_running_blocked()
        if anomalies:
            t = anomalies[0]
            return Envelope.ok(
                status=str(t.status),
                task_id=str(t.id),
                next=(
                    "log a reflect-note observing the anomaly via "
                    f"note(scope='reflect', task_id='{t.id}', text='...')"
                ),
                context_briefing=await self._briefing_for(auditor_agent_id, t.id),
            )
        return Envelope.ok(
            status="idle",
            task_id=None,
            next="no anomalies — i_am_idle",
            context_briefing=await self._briefing_for(auditor_agent_id, None),
        )
