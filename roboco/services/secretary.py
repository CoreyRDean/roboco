"""SecretaryService — the read/relay surfaces behind the CEO chief-of-staff.

The Secretary (INTENT.md §3, specs/03-secretary.md) is the CEO's two-way
conversational interface. This service backs the *read* half (company-state the
Secretary fetches to brief the CEO) and the *relay* half (carrying CEO intent
downward), composing existing services rather than introducing new machinery:

- ``status_summary`` — in-flight work by state, active blockers, recent
  activity, and spend-vs-budget. Sourced from ``TaskService`` data,
  ``DashboardService`` recent-activity, ``UsageService`` spend, and the
  ``BusinessGoals`` budget cap.
- ``action_queue`` — the CEO action queue: tasks awaiting CEO approval, board
  reviews ready for Approve & Start, human-resolvable blockers, and unacked
  CEO-targeted notifications (pitches/approvals).
- ``proactive_digest`` — the feed source for "what needs the CEO" (3.A2):
  pending approvals, stale decisions, drift off-goal, fresh pitches. Data only;
  delivery cadence is wired in Phase 5.
- ``relay_directive`` / ``apply_goal_edit`` — the downward side-effect executor
  (3.A1). The Secretary obeys the *same gate list* as the rest of the company:
  any directive whose action would trip a gate (spend, go_public,
  new_product_line, cap_breach) is NOT executed silently — it becomes a CEO
  action item instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import func, select

from roboco.db.tables import NotificationTable, TaskTable
from roboco.models.base import (
    BlockerResolverType as _BlockerResolverType,
)
from roboco.models.base import (
    NotificationType,
    TaskStatus,
)
from roboco.models.business_goals import BusinessGoalsUpdate, Objective, OperatingPolicy
from roboco.services.base import BaseService
from roboco.services.business_goals import BusinessGoalsService
from roboco.services.dashboard import get_dashboard_service
from roboco.services.notification import NotificationService
from roboco.services.usage import get_usage_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from roboco.db.tables import BusinessGoalsTable

# Task states that mean "work is in flight" — anything not terminal and not
# still sitting in the backlog waiting for PM setup. Drives the status summary's
# by-state breakdown so the CEO sees only live work.
_IN_FLIGHT_STATES: tuple[TaskStatus, ...] = (
    TaskStatus.PENDING,
    TaskStatus.CLAIMED,
    TaskStatus.IN_PROGRESS,
    TaskStatus.BLOCKED,
    TaskStatus.PAUSED,
    TaskStatus.VERIFYING,
    TaskStatus.NEEDS_REVISION,
    TaskStatus.AWAITING_QA,
    TaskStatus.AWAITING_DOCUMENTATION,
    TaskStatus.AWAITING_PM_REVIEW,
    TaskStatus.AWAITING_CEO_APPROVAL,
)

# Notification types that represent a request the CEO must act on. APPROVAL is
# the gate signal (board-review-complete, CEO escalation, pitches); ALERT is the
# free-form attention signal a relayed/escalated item carries.
_CEO_ACTIONABLE_NOTIFICATION_TYPES: tuple[NotificationType, ...] = (
    NotificationType.APPROVAL,
    NotificationType.ALERT,
)

# A decision/approval is "stale" once it has waited this long unacked. Used by
# the proactive digest to flag things drifting toward neglect. Tunable; the
# delivery cadence that consumes this lives in Phase 5.
_STALE_AFTER = timedelta(hours=48)


# =============================================================================
# GATE CLASSIFICATION (the leash — INTENT.md §6)
# =============================================================================
# A relayed directive carries an intent. Some intents would themselves trip a
# gate (spend money, go public, greenlight a product, breach a cap). The
# Secretary obeys the same gate list as everything else: gated intents are NOT
# executed silently — they are surfaced back to the CEO as action items. This
# classification is pure (no DB / no I/O) so it is unit-testable in isolation.

# The canonical gate vocabulary (mirrors OperatingPolicy.gate_list defaults).
_GATE_SPEND = "spend"
_GATE_GO_PUBLIC = "go_public"
_GATE_NEW_PRODUCT_LINE = "new_product_line"
_GATE_CAP_BREACH = "cap_breach"

# Keyword → gate mapping. Conservative: if a directive *reads like* a gated
# action, we gate it. False positives become a CEO action item (safe); only a
# false negative would silently execute a gated action (unsafe), so the mapping
# leans toward over-gating. The keys are substrings matched case-insensitively
# against the directive text.
_GATE_KEYWORDS: dict[str, str] = {
    "spend": _GATE_SPEND,
    "pay ": _GATE_SPEND,
    "payment": _GATE_SPEND,
    "purchase": _GATE_SPEND,
    "buy ": _GATE_SPEND,
    "budget increase": _GATE_SPEND,
    "domain": _GATE_SPEND,
    "subscribe": _GATE_SPEND,
    "subscription": _GATE_SPEND,
    "ad campaign": _GATE_SPEND,
    "paid ": _GATE_SPEND,
    "go public": _GATE_GO_PUBLIC,
    "make public": _GATE_GO_PUBLIC,
    "publish": _GATE_GO_PUBLIC,
    "launch publicly": _GATE_GO_PUBLIC,
    "ship to users": _GATE_GO_PUBLIC,
    "make the repo public": _GATE_GO_PUBLIC,
    "new product": _GATE_NEW_PRODUCT_LINE,
    "greenlight": _GATE_NEW_PRODUCT_LINE,
    "approve the pitch": _GATE_NEW_PRODUCT_LINE,
    "start a product": _GATE_NEW_PRODUCT_LINE,
    "launch a product": _GATE_NEW_PRODUCT_LINE,
    "exceed budget": _GATE_CAP_BREACH,
    "exceed the cap": _GATE_CAP_BREACH,
    "raise the cap": _GATE_CAP_BREACH,
    "more active products": _GATE_CAP_BREACH,
}


@dataclass(frozen=True)
class GateDecision:
    """Outcome of classifying a directive against the gate list.

    ``gated`` True means the action would trip a gate and must be surfaced to
    the CEO as an action item rather than executed. ``gate`` names which gate
    (one of the gate-list vocabulary) when gated; None otherwise.
    """

    gated: bool
    gate: str | None
    matched: str | None


def classify_directive(text: str, gate_list: list[str]) -> GateDecision:
    """Classify a relay directive against the active gate list.

    Pure function — no DB, no I/O. Matches the directive text against the gate
    keyword map; if the matched gate is in the active ``gate_list`` the
    directive is gated. A gate keyword whose gate is NOT in the active list (the
    CEO loosened the leash) passes through ungated.
    """
    lowered = text.lower()
    for keyword, gate in _GATE_KEYWORDS.items():
        if keyword in lowered and gate in gate_list:
            return GateDecision(gated=True, gate=gate, matched=keyword.strip())
    return GateDecision(gated=False, gate=None, matched=None)


# =============================================================================
# RELAY OUTCOME
# =============================================================================


@dataclass(frozen=True)
class RelayOutcome:
    """Result of a downward relay.

    ``executed`` True means the directive was delivered downward (a notification
    was sent). ``gated`` True means it was withheld and turned into a CEO action
    item instead. Exactly one of the two is True.
    """

    executed: bool
    gated: bool
    gate: str | None
    recipients: list[str]
    detail: str


class SecretaryService(BaseService):
    """Read + relay surfaces for the Secretary chief-of-staff."""

    service_name: ClassVar[str] = "secretary"

    # ------------------------------------------------------------------
    # READ SURFACES
    # ------------------------------------------------------------------

    async def status_summary(self) -> dict:
        """Compact company status: in-flight work, blockers, activity, spend.

        Reuses ``DashboardService`` for recent activity and ``UsageService`` for
        spend; the by-state and blocker breakdowns are direct aggregate queries
        (no per-row materialization) so this stays cheap to call conversationally.
        """
        in_flight = await self._tasks_by_state()
        blockers = await self._active_blockers()
        spend = await self._spend_vs_budget()

        dashboard = get_dashboard_service(self.session)
        recent = await dashboard.get_recent_activity(hours=24, limit=15)

        total_in_flight = sum(in_flight.values())
        return {
            "in_flight": {
                "total": total_in_flight,
                "by_state": in_flight,
            },
            "blockers": blockers,
            "spend": spend,
            "recent_activity": recent.get("activity", []),
            "generated_at": datetime.now(UTC).isoformat(),
        }

    async def action_queue(self) -> dict:
        """The CEO action queue — the short list of things needing the human.

        Four sources, all surfaced today (no Phase-6 dependency): tasks awaiting
        CEO approval, board reviews ready for Approve & Start, human-resolvable
        blockers (stranded work), and unacked CEO-targeted approval/alert
        notifications (pitches, escalations).
        """
        awaiting_ceo = await self._tasks_in_status(TaskStatus.AWAITING_CEO_APPROVAL)
        approve_and_start = await self._board_reviews_awaiting_start()
        stranded = await self._human_blocked_tasks()
        ceo_notifications = await self._ceo_actionable_notifications()

        items: list[dict] = []
        items.extend(
            self._task_item(
                t, kind="awaiting_ceo_approval", reason="CEO final approval"
            )
            for t in awaiting_ceo
        )
        items.extend(
            self._task_item(
                t,
                kind="approve_and_start",
                reason="Board review complete — approve & start",
            )
            for t in approve_and_start
        )
        items.extend(
            self._task_item(
                t, kind="stranded_blocker", reason="Blocked on a human decision"
            )
            for t in stranded
        )
        items.extend(self._notification_item(n) for n in ceo_notifications)

        return {
            "total": len(items),
            "items": items,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    async def cockpit_summary(self) -> dict:
        """Derived cockpit state (6.B1): "Is the business winning?" at a glance.

        Composed read-only from what already exists — no new measurement
        machinery: per-objective proxy progress and goal-coverage from the
        ``_drift_signals`` the digest already uses, spend-vs-budget from
        ``_spend_vs_budget`` (``UsageService`` projection vs the budget cap), and
        active-products-vs-cap from ``ProductService`` (every registered product
        counts as active — the same rule the strategy-cap gate enforces).

        Honest boundary (spec §"On winning"): there is no objective->task linkage
        in the data model, so per-objective progress is not a stored percentage —
        it is the coverage proxy the work engine itself uses. ``basis="proxy"``
        marks the whole summary as proxy until real external launches greenlit.
        """
        from roboco.services.product import get_product_service

        goals = await self._goals()
        drift = await self._drift_signals(goals)
        spend = await self._spend_vs_budget()
        policy = OperatingPolicy.model_validate(goals.operating_policy)

        # Per-objective proxy progress. Active objectives first (lower priority
        # value == higher priority), mirroring the strategy engine's ordering.
        # ``has_work_behind_it`` is the company-wide coverage proxy: there is no
        # per-objective task linkage today, so an objective is "covered" iff any
        # work is in flight at all (the same proxy `_strategy_assess` relies on).
        objectives = [Objective.model_validate(o) for o in goals.objectives]
        active = sorted(
            (o for o in objectives if o.status.value == "active"),
            key=lambda o: o.priority,
        )
        has_work = drift["in_flight_tasks"] > 0
        objective_items = [
            {
                "title": o.title,
                "priority": o.priority,
                "metric": o.metric,
                "target": o.target,
                "horizon": o.horizon,
                "has_work_behind_it": has_work,
            }
            for o in active
        ]

        # Active products vs cap. Products are not status-scoped, so every
        # registered product counts as active — identical to the orchestrator's
        # `_strategy_caps_ok`, so the cockpit and the gate agree on the number.
        products = await get_product_service(self.session).list_all(limit=1000)
        active_products = len(products)
        max_products = int(policy.max_active_products)

        return {
            "basis": "proxy",
            "objectives": objective_items,
            "goal_coverage": drift,
            "spend": spend,
            "products": {
                "active_products": active_products,
                "max_active_products": max_products,
                "at_cap": active_products >= max_products,
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }

    async def proactive_digest(self) -> dict:
        """The proactive-feed data source (3.A2): "what needs the CEO".

        Pending approvals + fresh pitches come from the action queue; stale
        decisions are the queue items that have aged past ``_STALE_AFTER``;
        drift is goals-derived — in-flight work and spend that map to no active
        objective, plus objectives with no work behind them. Data only; the
        cadence/channel that delivers it is Phase 5.
        """
        goals = await self._goals()
        queue = await self.action_queue()
        items = queue["items"]

        now = datetime.now(UTC)
        stale = [it for it in items if self._is_stale(it, now)]
        fresh_pitches = [
            it
            for it in items
            if it.get("kind") in ("approve_and_start", "awaiting_ceo_approval")
        ]
        drift = await self._drift_signals(goals)

        return {
            "pending_approvals": len(items),
            "stale_decisions": stale,
            "fresh_pitches": fresh_pitches,
            "drift": drift,
            "generated_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # RELAY / SIDE-EFFECT EXECUTOR (3.A1)
    # ------------------------------------------------------------------

    async def relay_directive(
        self,
        *,
        ceo_agent_id: UUID,
        directive: str,
        recipients: list[str],
    ) -> RelayOutcome:
        """Carry a CEO directive downward — or gate it.

        If the directive's intent would trip a gate, it is NOT delivered: a CEO
        action-item notification is raised back to the CEO instead, and the
        outcome reports ``gated=True``. Otherwise the directive is relayed to the
        named recipients (Board / Main PM) as an ack-required notification from
        the CEO. Reuses ``NotificationService`` — no new machinery.
        """
        goals = await self._goals()
        policy = OperatingPolicy.model_validate(goals.operating_policy)
        decision = classify_directive(directive, policy.gate_list)

        notifications = NotificationService()
        if decision.gated:
            # Gated: surface back to the CEO as an action item, do not execute.
            await notifications.send_ack_notification(
                from_agent=ceo_agent_id,
                to_agent="ceo",
                body=(
                    f"[GATED — needs your approval] The directive "
                    f'"{directive}" would trip the "{decision.gate}" gate, so it '
                    "was not relayed. Approve it explicitly to proceed."
                ),
            )
            self.log.info(
                "Secretary relay gated",
                gate=decision.gate,
                matched=decision.matched,
            )
            return RelayOutcome(
                executed=False,
                gated=True,
                gate=decision.gate,
                recipients=[],
                detail=(
                    f"Directive trips the '{decision.gate}' gate; raised as a "
                    "CEO action item instead of relaying."
                ),
            )

        # In-bounds: relay downward to each recipient as the CEO.
        delivered: list[str] = []
        for recipient in recipients:
            await notifications.send_ack_notification(
                from_agent=ceo_agent_id,
                to_agent=recipient,
                body=f"[CEO directive — via Secretary]\n\n{directive}",
            )
            delivered.append(recipient)
        self.log.info("Secretary relay delivered", recipients=delivered)
        return RelayOutcome(
            executed=True,
            gated=False,
            gate=None,
            recipients=delivered,
            detail=f"Relayed to {', '.join(delivered) or '(none)'}.",
        )

    async def apply_goal_edit(
        self,
        *,
        ceo_agent_id: UUID,
        north_star: str | None = None,
        objectives: list[Objective] | None = None,
        operating_policy: OperatingPolicy | None = None,
        constraints: list[str] | None = None,
    ) -> BusinessGoalsTable:
        """Apply a confirmed goal edit through ``BusinessGoalsService.update``.

        Goal changes the CEO makes conversationally land in the SAME singleton
        artifact the Panel edits (one place to tune — INTENT.md §9). The CEO-only
        check is the route's responsibility; this method assumes an authorized
        caller and writes the patch. Caller commits.
        """
        service = BusinessGoalsService(self.session)
        update = BusinessGoalsUpdate(
            north_star=north_star,
            objectives=objectives,
            operating_policy=operating_policy,
            constraints=constraints,
        )
        return await service.update(update, updated_by=ceo_agent_id)

    # ------------------------------------------------------------------
    # PRIVATE — read helpers
    # ------------------------------------------------------------------

    async def _goals(self) -> BusinessGoalsTable:
        return await BusinessGoalsService(self.session).get_or_initialize()

    async def _tasks_by_state(self) -> dict[str, int]:
        """Count in-flight tasks grouped by status (single aggregate query)."""
        result = await self.session.execute(
            select(TaskTable.status, func.count(TaskTable.id))
            .where(TaskTable.status.in_(_IN_FLIGHT_STATES))
            .group_by(TaskTable.status)
        )
        counts = {s.value: 0 for s in _IN_FLIGHT_STATES}
        for status_value, count in result.all():
            key = (
                status_value.value
                if hasattr(status_value, "value")
                else str(status_value)
            )
            counts[key] = int(count)
        return counts

    async def _active_blockers(self) -> dict:
        """Blocked tasks split by who must resolve them (agent vs human)."""
        result = await self.session.execute(
            select(TaskTable).where(TaskTable.status == TaskStatus.BLOCKED)
        )
        blocked = list(result.scalars().all())
        human = [
            t for t in blocked if t.blocker_resolver_type == _BlockerResolverType.HUMAN
        ]
        return {
            "total": len(blocked),
            "awaiting_human": len(human),
            "tasks": [self._task_brief(t) for t in blocked],
        }

    async def _spend_vs_budget(self) -> dict:
        """30-day spend and projected monthly cost against the budget cap."""
        usage = get_usage_service(self.session)
        summary = await usage.get_summary(period="30d")
        projection = await usage.get_projection()
        goals = await self._goals()
        policy = OperatingPolicy.model_validate(goals.operating_policy)
        budget = policy.monthly_budget_usd
        spent_30d = float(summary.get("total_cost_usd", 0.0))
        projected = float(projection.get("projected_monthly_cost_usd", 0.0))
        pct = round(projected / budget * 100, 1) if budget > 0 else None
        return {
            "monthly_budget_usd": budget,
            "spend_30d_usd": round(spent_30d, 4),
            "projected_monthly_usd": round(projected, 4),
            "projected_pct_of_budget": pct,
            "over_budget": budget > 0 and projected > budget,
        }

    async def _tasks_in_status(self, status: TaskStatus) -> list[TaskTable]:
        result = await self.session.execute(
            select(TaskTable)
            .where(TaskTable.status == status)
            .order_by(TaskTable.updated_at.desc().nullslast())
        )
        return list(result.scalars().all())

    async def _board_reviews_awaiting_start(self) -> list[TaskTable]:
        """Pending board tasks the board has finished — CEO's Approve & Start."""
        result = await self.session.execute(
            select(TaskTable)
            .where(
                TaskTable.status == TaskStatus.PENDING,
                TaskTable.board_review_complete.is_(True),
            )
            .order_by(TaskTable.updated_at.desc().nullslast())
        )
        return list(result.scalars().all())

    async def _human_blocked_tasks(self) -> list[TaskTable]:
        """Blocked tasks that only a human can clear — stranded work."""
        result = await self.session.execute(
            select(TaskTable)
            .where(
                TaskTable.status == TaskStatus.BLOCKED,
                TaskTable.blocker_resolver_type == _BlockerResolverType.HUMAN,
            )
            .order_by(TaskTable.updated_at.desc().nullslast())
        )
        return list(result.scalars().all())

    async def _ceo_actionable_notifications(self) -> list[NotificationTable]:
        """Unacked CEO-targeted approval/alert notifications (pitches, escalations)."""
        ceo_id = await self._ceo_agent_id()
        if ceo_id is None:
            return []
        result = await self.session.execute(
            select(NotificationTable)
            .where(
                NotificationTable.to_agents.contains([ceo_id]),
                NotificationTable.type.in_(_CEO_ACTIONABLE_NOTIFICATION_TYPES),
                ~NotificationTable.acked_by.contains([ceo_id]),
            )
            .order_by(NotificationTable.timestamp.desc())
            .limit(50)
        )
        return list(result.scalars().all())

    async def _ceo_agent_id(self) -> UUID | None:
        from roboco.db.tables import AgentTable
        from roboco.models.base import AgentRole

        result = await self.session.execute(
            select(AgentTable.id).where(AgentTable.role == AgentRole.CEO)
        )
        return result.scalar_one_or_none()

    async def _drift_signals(self, goals: BusinessGoalsTable) -> dict:
        """Goals-derived drift: objectives with no in-flight work behind them.

        A lightweight, honest proxy (INTENT.md §9 "drift") without claiming the
        full goal-coverage computation Phase 5 builds: count active objectives
        and the in-flight tasks, and flag the case where work is happening with
        no objectives set (pure drift) or objectives exist with zero in-flight
        work (stalled direction).
        """
        objectives = [Objective.model_validate(o) for o in goals.objectives]
        active = [o for o in objectives if o.status.value == "active"]
        in_flight_count = (
            await self.session.scalar(
                select(func.count(TaskTable.id)).where(
                    TaskTable.status.in_(_IN_FLIGHT_STATES)
                )
            )
        ) or 0
        return {
            "active_objectives": len(active),
            "in_flight_tasks": int(in_flight_count),
            "work_without_objectives": len(active) == 0 and in_flight_count > 0,
            "objectives_without_work": len(active) > 0 and in_flight_count == 0,
        }

    # ------------------------------------------------------------------
    # PRIVATE — item shaping
    # ------------------------------------------------------------------

    @staticmethod
    def _task_brief(task: TaskTable) -> dict:
        return {
            "task_id": str(task.id),
            "title": task.title,
            "status": task.status.value,
            "team": task.team.value if task.team else None,
            "priority": task.priority,
        }

    def _task_item(self, task: TaskTable, *, kind: str, reason: str) -> dict:
        updated = task.updated_at or task.created_at
        return {
            "kind": kind,
            "source": "task",
            "task_id": str(task.id),
            "title": task.title,
            "status": task.status.value,
            "team": task.team.value if task.team else None,
            "priority": task.priority,
            "pr_url": task.pr_url,
            "reason": reason,
            "updated_at": updated.isoformat() if updated else None,
        }

    @staticmethod
    def _notification_item(n: NotificationTable) -> dict:
        return {
            "kind": "notification",
            "source": "notification",
            "notification_id": str(n.id),
            "type": n.type.value if hasattr(n.type, "value") else str(n.type),
            "priority": n.priority.value
            if hasattr(n.priority, "value")
            else str(n.priority),
            "subject": n.subject,
            "reason": "Unacknowledged signal awaiting the CEO",
            "related_task_id": str(n.related_task_id) if n.related_task_id else None,
            "updated_at": n.timestamp.isoformat() if n.timestamp else None,
        }

    @staticmethod
    def _is_stale(item: dict, now: datetime) -> bool:
        raw = item.get("updated_at")
        if not raw:
            return False
        try:
            ts = datetime.fromisoformat(raw)
        except ValueError:
            return False
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return now - ts > _STALE_AFTER


def get_secretary_service(session: AsyncSession) -> SecretaryService:
    """Build a SecretaryService bound to a DB session."""
    return SecretaryService(session)
