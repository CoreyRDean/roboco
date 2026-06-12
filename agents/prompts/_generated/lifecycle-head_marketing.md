# Verbs available to your role (head_marketing)

These are the only verbs the gateway will accept from you. Calling any
other verb will be rejected with a Decision telling you the right one.

- **escalate_to_ceo**: Escalate to CEO with reason. Transitions to awaiting_ceo_approval.
- **i_am_idle**: Signal you have no active work. PMs auto-pause owned in_progress tasks.
- **pitch**: Author a new product PITCH grounded in the goals and research. Creates a root proposal task that lands in the CEO's Approve & Start queue (pending + board_review_complete). Greenlighting a new product line is gated, so this always reaches the CEO; on approval the system autonomously provisions the private repo(s) and seeds delivery. The verb composes no atomic action — it originates a NEW root task rather than transitioning an existing one, so the body owns the creation dispatch (mirrors board_triage's read-only special form).
- **triage**: List actionable tasks in your scope.
