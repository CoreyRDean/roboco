# Phase 2 — Web & Market Research

*Descriptive spec. See [INTENT.md](../INTENT.md) §5 (taxonomy of work), §10.*

## What this is

The company's ability to look at the **real world** — markets, competitors,
technologies, customers, trends — and not just at its own codebase. Genuine,
cited external research, available to the agents whose work depends on knowing
what is true outside the building.

## Why it matters

Every market decision, product pitch, brand, and positioning is worthless if it
is invented. Today the only "research" a RoboCo agent can do is search its own
repository and internal knowledge base — there is no window onto the world. A
company that ideates products and targets markets without seeing the market is
guessing. This phase makes research real, and as a side effect upgrades every
existing research task.

## What it must do

- **Give the right agents a window onto the world** — the Board and any
  research-tasked agent can gather external information relevant to the goals.
- **Produce research as durable, cited artifacts** — a research task yields a
  grounded finding that names its sources, not an unsourced opinion. Other agents
  and the CEO can build on it and trace where a claim came from.
- **Stay grounded** — claims about markets, competitors, or technologies are
  backed by what was actually found; the absence of evidence is stated rather
  than filled in.
- **Respect the guardrails** — research is observation. It reads the world; it
  does not act on it (no posting, buying, or contacting anyone). It is autonomous
  and cheap by policy, and bounded so it cannot run away.

## What good looks like

- A market-research task returns an analysis a skeptical CEO would trust — real
  competitors, real signals, real citations.
- The Head of Marketing can name a target market and defend it with evidence.
- A product pitch rests on findings someone could independently verify.
- When the world doesn't support a hypothesis, the research says so.

## Boundaries

- **Read-only on the world.** Any action that touches the outside (publishing,
  spending, outreach) belongs to gated phases, not here.
- Not a general web-automation or scraping platform — it serves research, framed
  by the goals, not arbitrary browsing.
- It informs decisions; it does not make them.

## Depends on

The existing `research` task type (which it makes genuinely useful). Strongest
when paired with Goals (Phase 1), so research aims at the objectives rather than
wandering.

## Open questions

- The breadth of sources the company should trust, and how freshness/quality is
  judged.
- Cost controls on research depth (how much is enough before marginal value falls
  below marginal cost).
- How citations are stored and surfaced so a finding stays traceable over time.
