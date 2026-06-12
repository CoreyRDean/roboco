# RoboCo — INTENT

> The north-star vision for RoboCo. This is a **living intent document**: it
> states what we are building toward and why, not how. Implementation plans,
> specs, and tickets derive from it. Keep it current as the vision sharpens.
>
> Status: draft v0.5 · Last updated 2026-06-12

---

## 1. North Star

**RoboCo is a company-in-a-box you run on your own computer.** A single human
is the **CEO and the only human in the company**. Everything else — strategy,
product ideation, market research, branding, engineering, QA, documentation,
go-to-market — happens autonomously under the hood, executed by a workforce of
AI agents organized like a real company.

The CEO does not write code, manage tasks, or spin up repositories. The CEO
**sets direction and makes the few decisions only a CEO should make.** The
company does the rest and surfaces work upward only when it genuinely needs a
human call.

The test we are building toward: *the CEO sets a business goal, walks away, and
the company researches a market, pitches a product, gets a yes, builds it,
ships it, and reports back — surfacing to the human only when something
irreversible, costly, or outside the guardrails needs approval.*

**The throughline:** the human supplies direction and judgment; the company
supplies everything else. Set nothing new and it still advances the standing
goals — it never sits idle while goal-aligned value remains.

---

## 2. The CEO experience

The human acts purely as a CEO. They have **two interfaces into the company**,
and nothing else:

1. **The Panel** — the visual cockpit. Performance, what's happening right now,
   status of every initiative, notifications, and a **queue of CEO-necessary
   actions**. This is where the CEO *watches* the company and acts on the few
   things that need them.
2. **The Secretary** — the conversational chief-of-staff. This is where the CEO
   *talks to* the company: set goals, discuss action items, send directives
   down, ask for status, get reminded of what matters.

Together they are the complete CEO surface. Everything below them is the company
running itself.

---

## 3. The Secretary (replaces the "Task Assistant")

The current "Task Assistant" / intake agent becomes the **Secretary** — the
human CEO's executive assistant and single conversational point of contact with
the company. It is far more than an intake interviewer. The Secretary:

- **Sets and updates goals** — captures and refines the CEO's north star,
  objectives, guardrails, and constraints into the live Business Goals.
- **Discusses action items** — walks the CEO through the CEO action queue:
  what needs a decision, why, the tradeoffs, the recommendation.
- **Communicates downward** — relays CEO directives and answers to the Board /
  Main PM; turns "I want X" into the right work or the right policy change.
- **Provides status updates** — synthesizes what's happening across the whole
  company: performance against goals, in-flight initiatives, blockers, spend.
- **Reminds the CEO** — proactively surfaces important things: pending
  approvals, decisions going stale, deadlines, things drifting off-goal.

The Secretary is **two-way**: it carries the CEO's intent down and the company's
state up. It is the human-facing voice of an otherwise autonomous company.

**Decided model:**

- **Authority** — the Secretary obeys the *same gate list* as the rest of the
  company. It adjusts goals, relays directives, and answers routine agent
  questions on the CEO's behalf autonomously; any action that would itself trip
  a gate (spend, going public, greenlighting a product) it brings back to the
  CEO. One coherent guardrail, not a separate permissions model.
- **Presence** — both proactive and on-demand: a quiet feed (reminders, a status
  digest, "pitches are waiting") *plus* an open chat. The proactive half is what
  makes it a real chief-of-staff rather than a fancier intake.
- **Scope** — the Secretary is the CEO's personal staff and interface; it does
  **not** do strategy itself. It maintains goals and translates intent; the
  **Board** pulls goals and produces strategy/pitches; the Secretary narrates
  that back up to the CEO.

---

## 4. The Panel — the cockpit

The Panel is the CEO's dashboard into a running company. It must answer, at a
glance: *Is the business winning? What is happening right now? What needs me?*

- **Performance** — progress against the CEO's goals and metrics; spend vs.
  budget; throughput; active product lines.
- **What's happening** — live view of initiatives, cells, agents, and work in
  flight.
- **Status** — health of every product/initiative and the org itself.
- **Notifications** — the formal signal stream.
- **CEO action queue** — the short list of things that actually need the human:
  product greenlights, spend approvals, going-public decisions, exceptions.

The CEO should be able to live almost entirely in "watch performance + clear the
queue" mode, dropping into the Secretary when they want to steer.

**On "winning" (the boundary):** a company-in-a-box produces *real* software and
brand assets locally, but real revenue and users require deploying to the world
— exactly what is gated (money, public, shipping). So performance is necessarily
**proxy** (products shipped, quality, velocity, goal-coverage) until the CEO
greenlights real external launches. Real-world growth happens *in the CEO's
queue*, by approving the company's bets — not by the company silently making
money. This is the boundary, by design, not a limitation to engineer away.

---

## 5. Two engines

RoboCo today is one engine. The vision is two, stacked — and the point is to
**keep the first untouched** and build the second on top.

**Delivery engine (exists, works).** Execution: a task flows Board → Main PM →
cells → build / QA / docs / merge, with CEO approval gates. Hand it a well-formed
task and it ships. This is the proven skeleton, and it stays exactly as is.

**Work-generation engine (to build) — the company's brain.** It turns the CEO's
north star into the *entire* stream of work the business needs — of every kind —
and feeds it into the delivery engine. This is the difference between a
*contractor* that executes what it's handed and a *company* that decides for
itself what to do. The human supplies direction and judgment; this engine
supplies everything else.

It runs a **continuous loop**:

```
assess state vs goals → find the highest-leverage gap or opportunity →
generate prioritized tasks → run them through the delivery engine →
measure → repeat
```

**The work it generates spans the whole business**, not just code:

- **New products** — research a market, ideate, pitch, and (on approval) build.
- **Iteration & maintenance** — improve, fix, and harden shipped products.
- **Research** — market, competitive, and technical investigation.
- **Brand, marketing & growth** — positioning, identity, content, launch.
- **Ops & infra** — the plumbing a running company needs.
- **Meta-work** — the company improving its own products, and itself.

**Prioritization & allocation.** Agent-effort and budget are finite, so the
engine allocates them across objectives by leverage and priority — choosing what
to do *next* and, just as importantly, what *not* to do now. The operating-policy
caps (budget, max active products) bound it.

**Continuity, and honest idle.** The company keeps working the goal-aligned
backlog on its own — it does not stop when the CEO walks away. It idles only when
there is genuinely no value-adding work left against the standing goals, and then
it surfaces *"I need direction"* rather than inventing busywork. **Value-driven,
never activity-driven.**

**Metrics close the loop.** Goal-coverage, drift, and per-objective progress
don't just render in the cockpit — they *feed* generation. Low coverage or drift
becomes either new aligned work or a misalignment surfaced to the CEO.

**One path through it — standing up a new product.** Most of the connective
tissue already exists; the pitch→approve→start surface is the CEO approval flow
we use today:

```
CEO sets Goals
   └─► work-gen loop: research → ideate → Board authors a PITCH
          └─► [GATE] lands in the CEO action queue
                 └─► CEO approves
                        └─► Provisioning: create private repo(s),
                            register project/product, seed delivery
                               └─► Delivery engine takes over
```

Other kinds of work (maintenance, research, marketing) flow the same way — minus
the provisioning step, and minus the gate when they fall inside the autonomy
line. New products are just the most visible output of the engine, not the
whole of it.

---

## 6. Autonomy & guardrails — **gated autonomy**

The company runs autonomously **between** approvals. It surfaces to the CEO only
for a defined set of high-stakes actions. Default posture: **gated autonomy.**

| Autonomous — no CEO approval | Gated — requires CEO approval |
|---|---|
| Market & competitive research | **Greenlighting a new product line** (the pitch) |
| Brand, positioning, GTM drafts | **Spending money** (domains, ads, paid services/APIs) |
| Internal planning | **Anything public/external** (making a repo public, publishing brand/marketing, shipping to real users) |
| Authoring pitches | **Exceeding budget or max-active-products caps** |
| Creating **private** repos for an already-approved product | |
| Delivery work within budget | |

Key property: **every new product still surfaces to the CEO** — the gate is on
the pitch. Autonomy lives in everything between approvals (research, drafts,
provisioning the approved thing, delivery). "Surface only when necessary" =
new product line, money, going public, or breaching a cap.

The autonomy level is itself **configurable** (propose-only ↔ gated ↔ full +
caps), so the CEO can tighten or loosen the leash over time.

---

## 7. Scope

- **Products are software + go-to-market.** A product is not just repos and
  features — brand, positioning, target market, and launch content are
  first-class deliverables. The Head of Marketing is a real producer, not only
  a reviewer.
- **Provisioning targets a dedicated, private GitHub org.** New repos are
  created **private**; going public is a separate, explicitly gated step.
- Both of these are **configurable**, not hardcoded.

---

## 8. Principle: everything is configurable

The CEO's levers are **software configuration, not constants in the code.**
Exposed and editable (via the Panel / Secretary):

- North star, objectives, success metrics, horizons
- Autonomy level and the gate list
- Monthly budget cap; max concurrent active products
- Repo provisioning target (org, default visibility)
- Constraints (e.g. "B2B only", "no crypto", tech preferences)
- Strategy-cycle cadence

If the CEO would ever want to change it, it lives in config — never baked in.

---

## 9. The Business Goals artifact

The single CEO-editable charter that every agent reads and the strategy engine
pursues. Edited through the Secretary or a Panel editor, and injected into every
agent's context briefing so all work orients to it. Conceptually **one place to
tune**, in four parts:

**Direction** *(CEO-set)*
- **north_star** — free text: the company's overarching mission.
- **constraints** — inviolable boundaries and preferences: e.g. "B2B only",
  "no crypto", "Rust + TypeScript preferred", brand voice, ethical lines.

**Objectives** *(CEO-set — the goals)* — a prioritized list; each has:
- **title** (short imperative), **description** (what success looks like)
- **metric** *(optional)*, **target** *(optional)*, **horizon** *(optional)*
- **priority**, **status** (active | achieved | paused | dropped)

Qualitative objectives are allowed — the metric is optional, because not
everything that matters is a number.

**Operating policy** *(CEO-set guardrails — the leash)*
- **autonomy_level** — propose_only | gated | full *(default: gated)*
- **gate_list** — actions that always need CEO approval: spend, go-public,
  new product line, cap breach *(editable set)*
- **monthly_budget_usd**, **max_active_products**
- **strategy_cadence** — off (human-triggered) | daily | weekly
- **provisioning** — github_org, default_repo_visibility (private), naming

**Derived** *(read-only, computed — surfaced in the cockpit)*
- per-objective progress (current vs target); spend vs budget; active vs cap
- **goal-coverage** — how much in-flight work actually maps to an objective
- **drift** — work or spend tied to no objective

Illustration:

```yaml
north_star: "Become the default workbench for solo AI developers."
constraints: ["B2B/prosumer", "no crypto", "Rust + TS", "calm, technical brand"]
objectives:
  - title: "Ship a usable v1 of one flagship product"
    metric: shipped   target: 1   horizon: "Q3 2026"   priority: 1   status: active
  - title: "Establish a credible brand + landing presence"
    metric: ~                     horizon: "Q3 2026"   priority: 2   status: active
operating_policy:
  autonomy_level: gated
  gate_list: [spend, go_public, new_product_line, cap_breach]
  monthly_budget_usd: 200
  max_active_products: 2
  strategy_cadence: weekly
  provisioning: { github_org: "<unset>", default_repo_visibility: private }
```

**Consumption.** Direction + active objectives + constraints are injected into
every agent's briefing (Board, PMs, Secretary). The Board pulls objectives to
generate strategy; the Secretary edits the whole artifact with the CEO; the
strategy engine respects operating policy; the cockpit renders the derived
metrics. **Changing goals is itself a logged decision** — the company should
notice and re-orient when direction shifts.

---

## 10. Where we are today (the skeleton)

Honest current state, so the gap is clear:

- **Delivery engine works**: intake draft → Board review → Main PM delegation →
  cells → build/QA/docs/merge, with working CEO approval gates.
- **Org structure exists**: Board (Product Owner, Head of Marketing, Auditor),
  Main PM, three cells (Backend, Frontend, UX/UI), each with devs/QA/PM/doc.
- **Products model exists but is only a mapping layer** — it groups *existing*
  repos; it cannot provision them.
- **No Business Goals** concept anywhere.
- **No autonomous origination** — the dispatcher only ever runs agents against
  work that already exists.
- **No repo creation** — only clone/branch/PR/push; project registration is
  manual-CEO-only.
- **No real web/market research** — agents have no external web access; today's
  "research" is internal-codebase only.
- **The Secretary is just an intake interviewer** today — human-triggered,
  drafts a single task, nothing more.
- **Failures strand work silently.** Observed: a PR merge refused by the repo's
  settings left a fully-built, reviewed, documented task stuck with an open PR
  and nothing surfaced — the cell just went idle. Stalls don't reach the CEO.

The bones are good. The vision is a large but tractable expansion of them.

---

## 11. Capabilities to build

1. **Business Goals** — a CEO-editable artifact (north star, objectives,
   metrics, guardrails, constraints) injected into every agent's context.
2. **Web/market research** — real external research tooling for the Board.
3. **The Secretary** — expand intake into the full two-way chief-of-staff.
4. **Work-generation loop** — let the company originate its own goal-aligned
   work (products, research, marketing, maintenance) and feed it to the delivery
   engine, surfacing only gated items to the CEO action queue.
5. **Provisioning** — create private org repo(s) + register project/product on
   approval, then seed delivery.
6. **Autonomous strategy cadence** — scheduled cycles + budget/concurrency caps.
7. **Panel as cockpit** — performance, status, what's-happening, action queue.
8. **Stall surfacing & recovery** — when work strands (a failed merge, a hard
   error, a corrupted task state), it must surface to the CEO action queue and
   be recoverable — never silently idle. A company that gets stuck without
   telling its CEO isn't autonomous; it's just unattended.

---

## 12. Phased roadmap (sequencing, not commitment)

1. **Goals** — the foundation everything reads. Standalone; improves existing
   agents immediately.
2. **Web research** — small, high value; makes pitches and GTM work real.
3. **Secretary v1** — goals + status + reminders + action-queue walkthrough.
4. **Pitch → Approve → Provision** — first "agent invented a product and stood
   it up" milestone.
5. **Autonomous cadence + caps** — the company runs cycles on its own; surfaces
   per the gate list.
6. **Cockpit polish** — performance/metrics views the CEO lives in.

Rationale: prove pitch *quality* with the human in the loop before automating
the trigger; provision only what's been approved; never let an autonomous loop
mint products before the CEO has seen the quality.

---

## 13. Open questions (living)

- **Which proxy metrics**: the "winning" boundary is settled (proxy until
  external launch — see §4); still open is *which* proxy metrics the cockpit
  leads with, and how goal-coverage is computed.
- **Identity of the company**: one company pursuing many products, or a holding
  structure spinning up distinct ventures?
- **Goals shape**: first draft in §9 — pending CEO redline on fields, the
  gate-list vocabulary, and which derived metrics matter.

---

## 14. Changelog

- **2026-06-12 — v0.5** — Reframed §5 from a narrow product-pitch "strategy
  engine" to a broad **work-generation engine** (the company's brain): the
  continuous decision loop, a taxonomy of autonomous work across the whole
  business, prioritization & allocation, continuity + honest idle
  (value-driven not activity-driven), and metrics closing the loop. Added the
  "human supplies direction, company supplies everything else" throughline to
  §1 and generalized capability #4 to a work-generation loop.
- **2026-06-12 — v0.4** — Added capability #8 "Stall surfacing & recovery" and
  a current-state note, after a real merge failure silently stranded a
  fully-built task (squash-merge refused by repo settings).
- **2026-06-12 — v0.3** — Added §9 The Business Goals artifact: four-part
  charter (direction / objectives / operating policy / derived), config-vs-
  derived split, and an illustrative schema. Renumbered later sections.
- **2026-06-12 — v0.2** — Secretary model decided: obeys the same gate list;
  proactive + on-demand presence; interface/translation role distinct from the
  Board's strategy role. Captured the "winning is proxy-until-launch" boundary
  in §4. Trimmed resolved open questions.
- **2026-06-12 — v0.1** — Initial north star: company-in-a-box, CEO-only human,
  two interfaces (Panel cockpit + Secretary), two engines (strategy on
  delivery), gated autonomy, software+GTM scope, private-org provisioning,
  everything-configurable principle, current-state skeleton, capabilities, and
  phased roadmap.
