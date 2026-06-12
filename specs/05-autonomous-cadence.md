# Phase 5 — Autonomous Cadence & Caps

*Descriptive spec. See [INTENT.md](../INTENT.md) §5 (the work-generation engine), §6.*

## What this is

The work-generation engine running **on its own** — the shift from a company that
acts when a human triggers it to one that decides for itself what to do next,
continuously, within budget and concurrency limits. This is the phase that makes
RoboCo a company you can actually walk away from.

## Why it matters

Everything before this still waits for a human to start a cycle. The promise of a
company-in-a-box is that the CEO sets direction and the company *keeps working* —
researching, building, maintaining, marketing, improving — surfacing only the
decisions that need a human. This phase is that promise made real, and it is the
one with the most to get right: an unbounded autonomous loop is also the easiest
way to waste money or mint garbage.

## What it must do

- **Run the decision loop continuously** — on its own cadence, the company
  assesses its state against the goals, finds the highest-leverage gap or
  opportunity, generates the work for it, feeds that work to the delivery engine,
  measures the result, and repeats.
- **Generate the full breadth of work** — not just new products, but iteration
  and maintenance of what's shipped, research, brand and marketing, ops, and the
  company improving itself. "Everything the business needs," chosen by what serves
  the goals.
- **Allocate finite effort by priority and leverage** — choose what to do next
  *and* what not to do now. Agent-effort and money are limited; the engine spends
  them where they matter most.
- **Stay within the caps** — the budget cap and the limit on active product lines
  bound it; it cannot exceed what the CEO declared in Operating Policy.
- **Honor the autonomy line** — gated actions (new product lines, spend, going
  public) surface to the CEO; everything inside the line just runs.
- **Idle honestly** — when there is genuinely no value-adding work left against
  the standing goals, it stops and asks the CEO for direction, rather than
  inventing busywork. **Value-driven, never activity-driven.**
- **Surface stalls** — when work strands (a failed step, a hard error, a stuck
  state), it reaches the CEO's queue and is recoverable, not silently dropped.

## What good looks like

- The CEO sets goals, closes the laptop, and returns to real progress plus a queue
  of only the decisions that needed them.
- Spend stays within cap; the number of concurrent products respects the limit.
- The company is busy when there is valuable work and quiet (and says so) when
  there isn't — never spinning to look productive.
- Nothing important fails in silence.

## Boundaries

- It does **not** loosen gates or exceed caps — autonomy is bounded by the goals
  and the operating policy, not "do anything."
- It does **not** replace the delivery engine — it *feeds* it.
- It is bounded by reality: the real-world growth actions (launch, spend, going
  public) it can only *propose*, never take unilaterally.

## Depends on

All prior phases — it is the engine that drives them. Goals (what to pursue),
Research (to see), the pitch/provision path (to act on products), the Secretary
(to surface), and the cockpit (to show). It is meaningfully the capstone.

## Open questions

- The cadence model — continuous, periodic, or event-driven — and how often the
  company should "think."
- How "highest-leverage" is judged when objectives compete for limited capacity.
- Runaway safety: the stops and circuit-breakers that keep an autonomous loop from
  burning budget or looping on low-value work.
- How "no value-adding work remains" is detected, so honest idle is real and not
  premature.
