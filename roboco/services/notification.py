"""
Notification Service

Sends notifications through the API with proper enforcement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from sqlalchemy import select

from roboco.db.base import get_db_context
from roboco.db.tables import AgentTable, NotificationTable
from roboco.models import NotificationPriority, NotificationType
from roboco.models.notification import CreateNotificationParams
from roboco.utils.converters import require_uuid

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


async def _resolve_agent_uuid(
    db: AsyncSession, value: str | UUID | None
) -> UUID | None:
    """Turn an agent slug or UUID (any case / any form) into a real UUID.

    `notifications.from_agent` is UUID-typed in the DB + FK to agents.id.
    Callers across the codebase pass slugs ("be-doc", "system", etc.) —
    this resolver does the slug→UUID translation. "system" resolves to
    the seeded system agent (stable UUID) so orchestrator-generated
    notifications always have a valid sender.

    Returns None only for truly absent values (None, empty string, or a
    slug we can't find). The caller in `_create_notification` logs +
    skips in that case rather than crashing on FK violation.
    """
    if value is None or value == "":
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        pass
    result = await db.execute(select(AgentTable).where(AgentTable.slug == str(value)))
    agent = result.scalar_one_or_none()
    return UUID(str(agent.id)) if agent else None


class NotificationService:
    """Service for sending system-generated notifications."""

    async def send_blocker_notification(
        self,
        task_id: str,
        blocker_reason: str,
        from_agent: str | None,
        to_pm: str,
    ) -> None:
        """Send notification about a blocked task."""
        logger.info(
            "Sending blocker notification",
            task_id=task_id,
            to_pm=to_pm,
        )

        # System notifications bypass normal permission checks
        body = (
            f"Task {task_id} has been blocked.\n\n"
            f"Reason: {blocker_reason}\n\n"
            "Please investigate and help resolve."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.BLOCKER_ESCALATION,
                priority=NotificationPriority.HIGH,
                from_agent=from_agent or "system",
                to_agents=[to_pm],
                subject=f"Task {task_id} is blocked",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_stuck_agent_notification(
        self,
        task_id: str,
        agent_slug: str,
        task_status: str,
        to_agent: str,
    ) -> None:
        """Alert an overseer that an agent is wedged in an unproductive loop.

        Raised when the dispatcher's respawn circuit-breaker pauses further
        spawns: the agent was respawned repeatedly without advancing the task,
        so automatic recovery has given up and a human needs to intervene.
        """
        logger.info(
            "Sending stuck-agent notification",
            task_id=task_id,
            agent=agent_slug,
            to_agent=to_agent,
        )
        body = (
            f"Agent {agent_slug} was repeatedly spawned on task {task_id} "
            f"(status: {task_status}) without advancing it, so further automatic "
            "spawns have been paused. Please investigate and intervene manually."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.BLOCKER_ESCALATION,
                priority=NotificationPriority.HIGH,
                from_agent="system",
                to_agents=[to_agent],
                subject=f"Agent {agent_slug} stuck on task {task_id}",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_stranded_task_notification(
        self,
        task_id: str,
        reason: str,
        to_ceo: str = "ceo",
        from_agent: str | None = None,
    ) -> None:
        """Surface a stranded task to the CEO action queue — never silently idle.

        Phase 5 (5.A1 — stall surfacing, INTENT.md §10 / §11 capability #8):
        the existing detectors cover respawn loops (``send_stuck_agent_
        notification``) and SLA drift (annotates the task), but a task that
        lands ``blocked`` and *waits for a human* — a HITL block, an auto-block
        from a failed step (the merge-405 / PR-base-422 we hit), a hard error,
        or a corrupted/stuck state — has no automatic resolver. Nothing spawns
        on it and no PM is guaranteed to look, so it can sit indefinitely while
        the company appears idle. This emits a formal ack-required BLOCKER
        notification to the CEO so the stranded work shows up as a recoverable
        action item in the cockpit / queue rather than rotting in silence.

        Idempotency: the caller fires this at most once per stall episode, and
        ``_create_notification``'s purpose-based dedup (same sender + type +
        ``related_task_id`` + recipient, still unacked) backstops it so a
        re-fire cannot spam the CEO.
        """
        logger.warning(
            "Sending stranded-task notification to CEO",
            task_id=task_id,
            reason=reason,
        )
        body = (
            f"Task {task_id} is stranded and will not advance on its own.\n\n"
            f"Reason: {reason}\n\n"
            "No automatic resolver can move it — it needs you to investigate and "
            "recover it (unblock, reassign, cancel, or fix the underlying cause). "
            "It is surfaced here so it is recoverable rather than silently idle."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.BLOCKER_ESCALATION,
                priority=NotificationPriority.HIGH,
                from_agent=from_agent or "system",
                to_agents=[to_ceo],
                subject=f"Task stranded — needs recovery: Task {task_id}",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_qa_ready_notification(
        self,
        task_id: str,
        from_agent: str | None,
        to_qa: str,
    ) -> None:
        """Send notification that task is ready for QA."""
        logger.info(
            "Sending QA ready notification",
            task_id=task_id,
            to_qa=to_qa,
        )

        body = (
            f"Task {task_id} is ready for QA review.\n\n"
            "Please review and provide feedback."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.REVIEW_REQUEST,
                priority=NotificationPriority.NORMAL,
                from_agent=from_agent or "system",
                to_agents=[to_qa],
                subject=f"Task {task_id} ready for QA",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_docs_ready_notification(
        self,
        task_id: str,
        from_agent: str | None,
        to_documenter: str,
    ) -> None:
        """Send notification that task is ready for documentation."""
        logger.info(
            "Sending docs ready notification",
            task_id=task_id,
            to_documenter=to_documenter,
        )

        body = (
            f"Task {task_id} has passed QA and is ready for documentation.\n\n"
            "Please create the required documentation."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.DOCUMENTATION_REQUEST,
                priority=NotificationPriority.NORMAL,
                from_agent=from_agent or "system",
                to_agents=[to_documenter],
                subject=f"Task {task_id} needs documentation",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_handoff_notification(
        self,
        task_id: str,
        handoff_id: str,
        from_agent: str | None,
        to_documenter: str,
    ) -> None:
        """Send notification that task needs handoff documentation."""
        logger.info(
            "Sending handoff notification",
            task_id=task_id,
            handoff_id=handoff_id,
            to_documenter=to_documenter,
        )

        body = (
            f"Task {task_id} is ready for handoff (ID: {handoff_id}).\n\n"
            "Please review and create handoff documentation."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.DOCUMENTATION_REQUEST,
                priority=NotificationPriority.NORMAL,
                from_agent=from_agent or "system",
                to_agents=[to_documenter],
                subject=f"Handoff required: Task {task_id}",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_qa_failed_notification(
        self,
        task_id: str,
        qa_notes: str,
        to_developer: str,
    ) -> None:
        """Send notification that task failed QA."""
        logger.info(
            "Sending QA failed notification",
            task_id=task_id,
            to_developer=to_developer,
        )

        body = (
            f"Task {task_id} has failed QA review.\n\n"
            f"Notes: {qa_notes}\n\n"
            "Please address the issues and resubmit."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.REVIEW_REQUEST,
                priority=NotificationPriority.HIGH,
                from_agent="system",
                to_agents=[to_developer],
                subject=f"QA Failed: Task {task_id}",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_board_review_complete_notification(
        self,
        task_id: str,
        from_agent: str | None = None,
        to_ceo: str = "ceo",
    ) -> None:
        """Tell the CEO a board review is complete and ready for Approve & Start.

        Board-reviewed coordination tasks stay ``pending`` and wait for the
        CEO's Approve & Start gate (``TaskService.approve_and_start``). The
        Product Owner + Head of Marketing record their review via channel
        dialogue and journal notes, but that left the CEO with no actionable
        signal — only buried chatter. This emits a
        formal APPROVAL notification (ack-required) carrying ``related_task_id``
        so the handoff is a real signal the panel can surface, not channel
        noise. Board roles are exactly the senders permitted to notify, so the
        orchestrator emits it as ``system`` on their behalf once BOTH board
        reviewers (PO + Head of Marketing) have finished.
        """
        logger.info(
            "Sending board-review-complete notification to CEO",
            task_id=task_id,
            to_ceo=to_ceo,
        )

        body = (
            f"Board review complete for task {task_id}.\n\n"
            "The Product Owner and Head of Marketing have both reviewed and "
            "recorded their requirements. The task is ready for your "
            "Approve & Start decision (hand to Main PM) or rejection."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.APPROVAL,
                priority=NotificationPriority.HIGH,
                from_agent=from_agent or "system",
                to_agents=[to_ceo],
                subject=f"Board review complete: Task {task_id}",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_pitch_ready_notification(
        self,
        task_id: str,
        title: str | None = None,
        from_agent: str | None = None,
        to_ceo: str = "ceo",
    ) -> None:
        """Tell the CEO the Board authored a new product PITCH awaiting greenlight.

        A pitch (Phase 4) is born already board-reviewed — the authoring Board
        roles ARE the board — so it skips the two-reviewer dispatch that
        ``send_board_review_complete_notification`` backs and needs its own
        actionable signal. Like that helper this emits a formal APPROVAL
        notification (ack-required) carrying ``related_task_id`` so the pitch is
        a real signal the panel's CEO action queue surfaces, not channel noise.
        The distinct subject names it as a *product greenlight* (a gated
        decision — INTENT.md §6) rather than a routine coordination handoff.
        """
        logger.info(
            "Sending pitch-ready notification to CEO",
            task_id=task_id,
            to_ceo=to_ceo,
        )

        named = f" '{title}'" if title else ""
        body = (
            f"The Board has authored a new product PITCH{named} (task {task_id}).\n\n"
            "It is grounded in the company goals and research and is ready for "
            "your Approve & Start decision. Greenlighting a new product line is "
            "gated, so this needs you. On approval the system autonomously "
            "provisions the private repo(s) and seeds the first delivery work."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.APPROVAL,
                priority=NotificationPriority.HIGH,
                from_agent=from_agent or "system",
                to_agents=[to_ceo],
                subject=f"New product pitch awaiting approval: Task {task_id}",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_pitch_provisioning_failed_notification(
        self,
        task_id: str,
        reason: str,
        from_agent: str | None = None,
        to_ceo: str = "ceo",
    ) -> None:
        """Surface a failed pitch provisioning to the CEO — never strand silently.

        Provisioning an approved pitch (create private repo(s), register the
        project/product, seed delivery) is autonomous because the CEO already
        said yes. But a failure there must NOT leave the approval half-applied
        and silent (INTENT.md §11 capability #8 — stall surfacing). This emits a
        formal ack-required notification to the CEO with the concrete reason and
        the remediation so the approval is recoverable rather than wedged.
        """
        logger.warning(
            "Sending pitch-provisioning-failed notification to CEO",
            task_id=task_id,
            reason=reason,
        )
        body = (
            f"Provisioning for the approved pitch (task {task_id}) did not "
            f"complete.\n\nReason: {reason}\n\n"
            "The approval is recorded but the private repo(s) / delivery seeding "
            "did not finish. Resolve the cause (commonly a missing provisioning "
            "org or token) and re-approve — provisioning is idempotent, so a "
            "retry will not double-create."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.BLOCKER_ESCALATION,
                priority=NotificationPriority.HIGH,
                from_agent=from_agent or "system",
                to_agents=[to_ceo],
                subject=f"Pitch provisioning failed: Task {task_id}",
                body=body,
                related_task_id=task_id,
            )
        )

    async def send_cap_breach_notification(
        self,
        cap: str,
        detail: str,
        from_agent: str | None = None,
        to_ceo: str = "ceo",
    ) -> None:
        """Tell the CEO an autonomous strategy cycle hit an operating-policy cap.

        Phase 5 (5.E2): a strategy cycle that *would* breach a cap (monthly
        budget or max active products) does NOT proceed — exceeding a cap is a
        gated action (INTENT.md §6). Instead of spending or minting a product
        over the line, the cycle surfaces the breach to the CEO as an
        ack-required action item so the human can raise the cap, pause work, or
        re-prioritise. ``cap`` names which limit (``budget`` / ``products``);
        ``detail`` carries the concrete numbers.
        """
        logger.warning(
            "Sending cap-breach notification to CEO",
            cap=cap,
            detail=detail,
        )
        body = (
            f"The autonomous strategy engine paused: continuing would breach the "
            f"'{cap}' cap in your operating policy.\n\n{detail}\n\n"
            "Exceeding a cap is gated, so the cycle stopped rather than spending "
            "or starting work over the line. Raise the cap, pause active work, or "
            "re-prioritise — then the next cycle will resume within the new "
            "bounds."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.APPROVAL,
                priority=NotificationPriority.HIGH,
                from_agent=from_agent or "system",
                to_agents=[to_ceo],
                subject=f"Strategy paused — '{cap}' cap reached",
                body=body,
            )
        )

    async def send_need_direction_notification(
        self,
        detail: str,
        from_agent: str | None = None,
        to_ceo: str = "ceo",
    ) -> None:
        """Tell the CEO the company has no value-adding work left against goals.

        Phase 5 (5.E3 — honest idle): when a strategy cycle finds genuinely no
        in-bounds, value-adding work to do against the standing goals, the
        company STOPS rather than inventing busywork (INTENT.md §5 — value-
        driven, never activity-driven). It emits this single "need direction"
        signal so the CEO knows to set new goals or raise a cap. Fires once per
        idle episode; the loop re-arms it only after real work appears again.
        """
        logger.info(
            "Sending need-direction notification to CEO",
            detail=detail,
        )
        body = (
            "The company has no value-adding, in-bounds work left against the "
            f"current goals.\n\n{detail}\n\n"
            "Rather than invent busywork, the strategy engine has gone quiet and "
            "is asking for direction: set or sharpen a goal, adjust the operating "
            "policy, or confirm there's nothing to do right now."
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.APPROVAL,
                priority=NotificationPriority.NORMAL,
                from_agent=from_agent or "system",
                to_agents=[to_ceo],
                subject="Need direction — no value-adding work against goals",
                body=body,
            )
        )

    async def send_ack_notification(
        self,
        *,
        from_agent: UUID | str,
        to_agent: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        task_id: UUID | str | None = None,
    ) -> None:
        """Send a free-form ack-required notification (PM/Board only).

        Used by the gateway `notify` content-tool. Distinguishes from
        the typed `send_*_notification` helpers above, which carry
        lifecycle semantics (blocker, qa-ready, etc.). Here the caller
        supplies the body verbatim. ALERT type is used so consumers
        treat it as a high-attention formal signal rather than
        conflating with task-state-driven notifications. The subject
        is derived from the first line of `body` (truncated), matching
        how `say`/`dm` derive a subject from free text.
        """
        subject = body.split("\n", 1)[0][:200] or "Notification"
        related_task_id = str(task_id) if task_id is not None else None
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.ALERT,
                priority=priority,
                from_agent=str(from_agent),
                to_agents=[to_agent],
                subject=subject,
                body=body,
                related_task_id=related_task_id,
            )
        )

    async def send_a2a_notification(
        self,
        task_id: str,
        a2a_context: dict[str, Any],
    ) -> None:
        """Send notification for A2A request (when recipient is busy or offline).

        Args:
            task_id: Related task ID
            a2a_context: Dict with from_agent, to_agent, skill, message,
                priority. `priority` is a `NotificationPriority` (full
                tristate: NORMAL / HIGH / URGENT). This key used to be
                `urgent: bool`, which collapsed HIGH to NORMAL —
                A2AService now sends Priority directly.
        """
        from_agent = a2a_context.get("from_agent", "unknown")
        to_agent = a2a_context.get("to_agent", "")
        skill = a2a_context.get("skill", "general")
        message = a2a_context.get("message", "")
        priority = a2a_context.get("priority", NotificationPriority.NORMAL)
        # Defensive coerce — accept enum, str, or a stray bool from a
        # legacy caller. The point is that HIGH survives, so only collapse
        # to URGENT/NORMAL if the input is genuinely a bool.
        if isinstance(priority, bool):
            priority = (
                NotificationPriority.URGENT if priority else NotificationPriority.NORMAL
            )
        elif not isinstance(priority, NotificationPriority):
            try:
                priority = NotificationPriority(str(priority))
            except ValueError:
                priority = NotificationPriority.NORMAL

        logger.info(
            "Sending A2A notification",
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            skill=skill,
            priority=priority.value,
        )

        # Cosmetic [URGENT] prefix stays urgent-only. HIGH is recorded at
        # the NotificationTable.priority column but gets no body/subject
        # prefix — the column is the source of truth for routing, the
        # label is just an attention hint for the human-readable body.
        urgency_label = "[URGENT] " if priority == NotificationPriority.URGENT else ""
        body = (
            f"{urgency_label}A2A request from {from_agent}.\n\n"
            f"Skill: {skill}\n\n"
            f"Message: {message}"
        )
        await self._create_notification(
            CreateNotificationParams(
                notification_type=NotificationType.A2A_REQUEST,
                priority=priority,
                from_agent=from_agent,
                to_agents=[to_agent],
                subject=f"{urgency_label}A2A: {skill}",
                body=body,
                related_task_id=task_id,
            )
        )

    @staticmethod
    def _notification_type_label(params: CreateNotificationParams) -> str:
        """Render the notification_type for a log line."""
        nt = params.notification_type
        return nt.value if hasattr(nt, "value") else str(nt)

    async def _resolve_recipients(
        self, db: Any, params: CreateNotificationParams
    ) -> list[UUID]:
        """Resolve to_agents (slugs/UUIDs) to UUID list. Drops unresolvable.

        notifications.to_agents is UUID[] — callers across the codebase
        pass slugs ("be-dev-1", "be-qa"). Resolve every recipient before
        insert; drop (with warn) any that don't resolve instead of
        letting asyncpg crash with "invalid UUID 'be-dev-1'".
        """
        to_agents_uuids: list[UUID] = []
        unresolved: list[str] = []
        for recipient in params.to_agents:
            resolved = await _resolve_agent_uuid(db, recipient)
            if resolved is None:
                unresolved.append(str(recipient))
            else:
                to_agents_uuids.append(resolved)
        if unresolved:
            logger.warning(
                "Dropping unresolved notification recipients",
                unresolved=unresolved,
                type=self._notification_type_label(params),
                subject=params.subject[:80],
            )
        return to_agents_uuids

    async def _create_notification(self, params: CreateNotificationParams) -> None:
        """Create a notification via the database and deliver it."""
        async with get_db_context() as db:
            from_agent_uuid = await _resolve_agent_uuid(db, params.from_agent)
            if from_agent_uuid is None:
                # notifications.from_agent is NOT NULL + FK to agents.id, so
                # we cannot insert. Skip-with-warn rather than crash the
                # upstream request.
                logger.warning(
                    "Skipping notification: from_agent unresolvable",
                    from_agent_input=str(params.from_agent),
                    type=self._notification_type_label(params),
                    subject=params.subject[:80],
                    to_agents=[str(a) for a in params.to_agents],
                )
                return
            to_agents_uuids = await self._resolve_recipients(db, params)
            if not to_agents_uuids:
                logger.warning(
                    "Skipping notification: no resolvable recipients",
                    to_agents_input=[str(a) for a in params.to_agents],
                    type=self._notification_type_label(params),
                    subject=params.subject[:80],
                )
                return
            # Purpose-based dedup (CEO directive, 2026-06-10): do NOT create a
            # second notification for the SAME purpose — same sender, same type,
            # same task, overlapping recipients — while a prior one is still
            # unacknowledged. Agents loop and re-send the same signal (often
            # reworded); each copy inflates the recipient's unacked set, which
            # soft-blocks their i_am_idle and drives respawn churn. A different
            # type, a different task, a different sender, or a recipient who has
            # already acked all go through. Body text is NOT compared, so
            # rewording cannot defeat the guard.
            related = params.related_task_id
            dup_q = (
                select(NotificationTable.id)
                .where(NotificationTable.from_agent == from_agent_uuid)
                .where(NotificationTable.type == params.notification_type)
                .where(NotificationTable.to_agents.overlap(to_agents_uuids))
                .where(~NotificationTable.acked_by.contains(to_agents_uuids))
                .where(
                    NotificationTable.related_task_id == related
                    if related is not None
                    else NotificationTable.related_task_id.is_(None)
                )
                .limit(1)
            )
            if await db.scalar(dup_q) is not None:
                logger.info(
                    "Suppressed duplicate notification (same purpose, unacked)",
                    from_agent=str(from_agent_uuid),
                    type=params.notification_type.value,
                    related_task_id=str(related) if related is not None else None,
                    to_agents=[str(a) for a in to_agents_uuids],
                )
                return
            notification = NotificationTable(
                type=params.notification_type,
                priority=params.priority,
                from_agent=from_agent_uuid,
                to_agents=to_agents_uuids,
                subject=params.subject,
                body=params.body,
                related_task_id=params.related_task_id,
            )
            db.add(notification)
            await db.flush()

            # Deliver via Redis Streams for real-time push
            from roboco.services.notification_delivery import (
                get_notification_delivery_service,
            )

            delivery_service = get_notification_delivery_service(db)
            await delivery_service.deliver(require_uuid(notification.id))

            await db.commit()

            logger.info(
                "Notification created and delivered",
                notification_id=str(notification.id),
                type=params.notification_type.value,
            )
