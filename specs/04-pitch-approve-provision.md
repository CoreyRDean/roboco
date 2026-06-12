# Phase 4 — Pitch → Approve → Provision

*Descriptive spec. See [INTENT.md](../INTENT.md) §5 (one path through the engine).*

## What this is

The end-to-end path where the **company originates a new product**, the CEO
greenlights it, and the system **stands it up automatically** — research and idea
become a real repository with work underway, without the CEO setting anything up.
It is the most visible single path through the work-generation engine, and the
first moment the company demonstrably acts like a company rather than a contractor.

## Why it matters

It proves the whole thesis in one loop: the company can decide *what* to build,
not just build what it's told. And it removes the concrete pain the CEO named —
having to invent product ideas and hand-configure repositories. A "yes" should be
all it takes.

## What it must do

- **Let the company author a pitch** — the Board, grounded in the goals and real
  research, produces a well-formed proposal for a new product (or feature, or
  go-to-market move): what it is, why it serves an objective, what success looks
  like, and what it would take. A pitch is a credible bet, not a thought.
- **Surface it as a clean CEO decision** — the pitch lands in the CEO action
  queue with its reasoning visible, and offers a clear choice: approve, reject, or
  keep discussing. Greenlighting a new product line is gated — this always reaches
  the human.
- **On approval, provision the reality** — create the private repository (or
  repositories, one per participating cell) in the dedicated org, register the
  project/product so the company knows it exists, seed the initial delivery work,
  and hand off to the existing delivery engine. The CEO does none of this.
- **Honor the autonomy line** — *deciding* to start a product is gated;
  *executing* an approved product (provisioning its private repos, seeding work)
  is autonomous, because the human already said yes.

## What good looks like

- The CEO opens the queue to find a credible product they did not ask for, with a
  rationale tied to a goal.
- One decision — approve — and shortly after there is a real private repo with
  the first work in flight. No manual setup, no copy-pasting tokens.
- A rejected pitch costs nothing and teaches the company something about the
  CEO's taste.

## Boundaries

- Cycles may still be **human-triggered** at this phase — the company doesn't yet
  run them on its own (that's Phase 5). This phase is about the *path*, not the
  cadence.
- **Private only.** Provisioning creates private repositories; making anything
  public, or any spend, remains separately gated.
- It is **one** path through the engine. Maintenance, research, and marketing work
  flow the same shape, minus provisioning — this phase doesn't claim to be the
  whole engine.

## Depends on

Business Goals (Phase 1) and Research (Phase 2) for credible pitches; the existing
CEO approval surface (already built — the "Approve & Start" gate); a new
provisioning capability (repo creation + project/product registration); the
Secretary (Phase 3) to narrate the pitch and the decision.

## Open questions

- The quality bar for a pitch, and what a "well-formed" pitch must contain to be
  worth the CEO's attention.
- Repository naming, templating, and how a multi-cell product maps to repos.
- What "seed the initial delivery work" should look like so the cells start well.
