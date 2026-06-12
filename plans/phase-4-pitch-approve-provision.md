# Plan — Phase 4: Pitch → Approve → Provision

Implements [`../specs/04-pitch-approve-provision.md`](../specs/04-pitch-approve-provision.md).
The Board originates a product pitch → it surfaces to the CEO queue → on approval
the system creates the private repo(s), registers the project/product, and seeds
delivery.

**Phase dependencies:** **Blocked by Phase 1 complete** (pitches read goals). **Soft:**
Phase 2 (research grounds pitch quality). The **provisioning sub-track (Track A/E)
is independent of Phase 1** and can start immediately. **Blocks:** Phase 5.

**Critical path:** pitch `4.D1 → 4.E1 → 4.B1 → 4.C1`; provision `4.A1 → 4.A2 → 4.E2`,
joined at approval (`4.E2` consumes the approved pitch).

---

## Track A — Data/Backend (provisioning — start now)

**4.A1 — GitHub repo-creation service.**
New `roboco/services/github_provisioning.py` (or extend `roboco/services/git.py`).
There is **no repo creation today** — only clone/branch/PR
(`services/git.py`, `services/workspace.py:583-890`). Add `create_repository(name,
description, private, org)` calling the GitHub REST API (`POST /orgs/{org}/repos`,
private by default — INTENT §7) with the org PAT. Return clone url + html url.
→ Blocked by: nothing — start immediately.

**4.A2 — Product/project registration from an approved pitch.**
A service path that, given an approved pitch, creates the private repo(s) via `4.A1`,
registers each as a Project (`roboco/services/project.py:56-123`,
`ProjectService.create`) and, for multi-cell, a Product
(`roboco/services/product.py`), then seeds the initial delivery task(s)
(`TaskService.create`, `roboco/services/task.py:537`).
→ Blocked by: 4.A1.

---

## Track D — Agent/Gateway (pitch authoring)

**4.D1 — A Board "pitch" verb.**
Add a `pitch` `IntentSpec` to `roboco/foundation/policy/lifecycle.py:765`
(allowed_roles = Product Owner + Head of Marketing) that creates a root task
representing a product proposal in a state that surfaces to the CEO. Implement the
verb in the Choreographer (mixin pattern,
`roboco/services/gateway/choreographer/qa.py:94-180` as the exemplar), expose it on
the flow MCP server (`roboco/mcp/flow_server.py`) and in `role_config.py`. Run
`make lifecycle` to regenerate the verb-surface artifacts.
→ Blocked by: Phase 1 complete (pitches must read goals).

**4.D2 — Pitch content contract.**
Define what a well-formed pitch carries (name, the objective it serves, what it
builds, the work per cell, success criteria, rationale grounded in research). Reuse
the draft shape from intake's `propose_draft`
(`roboco/agent_sdk/intake_driver.py:294-349`) as the structural model.
→ Blocked by: 4.D1.

---

## Track E — Orchestrator (surface + provision-on-approve)

**4.E1 — Surface pitches to the CEO action queue.**
Reuse the board-review→CEO handoff machinery
(`roboco/runtime/orchestrator.py:5762-5809`,
`_maybe_handoff_board_review_to_ceo` + `send_board_review_complete_notification`,
`services/notification.py:245-286`). A pitch should land in the same CEO queue with
an Approve & Start decision (the queue surface already exists from prior work).
→ Blocked by: 4.D1.

**4.E2 — Provision on approval.**
Hook the approval path (`approve_and_start`, `roboco/services/task.py:3867-3922`):
when the approved task is a pitch, invoke `4.A2` to create repos + register
project/product + seed delivery, then continue handing to Main PM. Provisioning is
autonomous because the CEO already said yes; failures surface (don't strand).
→ Blocked by: 4.A2, 4.E1.

---

## Track B — API / Track C — Panel

**4.B1 — Pitch decision endpoints.**
Reuse the existing CEO approval endpoints
(`approve-and-start`/`ceo-reject`, `roboco/api/routes/tasks.py:1359,1406`). Add only
pitch-specific response fields if the card needs them.
→ Blocked by: 4.E1.

**4.C1 — Pitch card in the CEO queue.**
Extend the CEO approval queue
(`panel/src/components/dashboard/ceo-approval-queue.tsx`) so a pitch renders with
its rationale and an Approve & Start / Reject action. The queue + Approve & Start
surface already exist — this adds the pitch presentation.
→ Blocked by: 4.B1.

---

## Parallelization summary

- **Start now (no Phase 1 needed):** the whole provisioning sub-track
  `4.A1 → 4.A2`.
- **After Phase 1:** the pitch sub-track `4.D1 → {4.D2, 4.E1}`; then
  `4.B1 → 4.C1`.
- **Join:** `4.E2` needs both `4.A2` (provisioning) and `4.E1` (surfacing).
- **Phase is "complete"** when a Board-authored pitch can be approved in the queue
  and a private repo with seeded work appears — the gate Phase 5 waits on.
