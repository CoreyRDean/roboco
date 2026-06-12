# Phase 3 — The Secretary

*Descriptive spec. See [INTENT.md](../INTENT.md) §3. Replaces the "Task Assistant".*

## What this is

The CEO's executive chief-of-staff and **single conversational interface** into
the company. It is the human-facing voice of an otherwise autonomous business:
the CEO talks to the Secretary, and the Secretary talks to — and for — the
company. It is the evolution of today's intake interviewer into something far
broader.

## Why it matters

A CEO running a company-in-a-box should not manage tasks, chase status, or read
agent channels. They should be able to *talk to their company*: state what they
want, hear how things are going, and act on the few things that need them. The
Secretary is that relationship. Together with the Panel (the watch surface), it
is the CEO's entire interface — everything else runs underneath.

## What it must do

- **Set and revise goals** — turn the CEO's words into the Business Goals
  artifact; help refine a vague intention into a clear north star, objectives,
  and limits.
- **Brief the CEO** — synthesize what is happening across the whole company:
  performance against goals, what's in flight, what's blocked, what's been spent.
  A status update on demand, in plain language.
- **Walk the CEO through the action queue** — for each thing that needs a human:
  what it is, why it needs them, the tradeoffs, and a recommendation. Turn a queue
  of decisions into a guided conversation.
- **Carry intent downward** — relay the CEO's directives and answer routine agent
  questions on the CEO's behalf, within the gate list. Translate "I want X" into
  the right goal change or the right work.
- **Remind, proactively** — surface pending approvals, decisions going stale,
  drift off-goal, fresh pitches. A quiet proactive feed *plus* an open chat, so
  nothing important waits unseen.
- **Obey the same gate list as everything else** — it acts autonomously on
  reversible, in-bounds things, and brings anything that would trip a gate (spend,
  going public, greenlighting a product) back to the CEO. One coherent guardrail,
  not a separate permission model.

## What good looks like

- The CEO can run the company through conversation and clearing the queue.
- The Secretary can answer "how are we doing?" with a synthesis the CEO trusts.
- The CEO is never surprised by something the Secretary should have surfaced.
- When the CEO says "tell the team to prioritize X," it happens — within bounds —
  without the CEO touching a task.

## Boundaries

- **It is not a strategist.** It maintains goals and translates intent; the Board
  produces strategy and pitches. The Secretary narrates that work up, it doesn't
  do it.
- **It is not an executor.** It doesn't build products; it represents the CEO to
  the parts of the company that do.
- **It does not bypass gates.** Its autonomy ends exactly where the CEO's gate
  list begins.

## Depends on

Business Goals (Phase 1) — its first and most important job is helping fill them.
The action queue (the existing approval surface, matured in Phase 6). It reads
broadly across the company's state.

## Open questions

- The default downward authority (how much it may decide/answer on the CEO's
  behalf) — likely configurable, with a conservative default.
- Its proactive cadence and channel — how often and how loudly it pings.
- How it represents the CEO to agents, and how agents know a Secretary relay
  carries CEO intent.
