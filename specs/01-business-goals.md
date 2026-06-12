# Phase 1 — Business Goals

*Descriptive spec. See [INTENT.md](../INTENT.md) §9. Foundation phase.*

## What this is

The single, CEO-owned charter that states what the company is trying to do and
within what limits — and that every agent reads and the work-generation engine
pursues. It is the one place the CEO tunes the company's direction and leash.

## Why it matters

Nothing downstream is possible without it. Today agents have no notion of "what
business outcome should we collectively achieve" — they execute whatever task
exists. Goals is the orientation layer: it turns a pile of agents into a company
with a purpose. Every later phase reads from it.

## What it must do

- **Let the CEO express direction in plain terms** — a north star (the
  overarching mission), a prioritized set of objectives (each with, optionally, a
  metric, target, and horizon — qualitative objectives are first-class because
  not everything that matters is a number), and the constraints the company must
  always respect (markets to avoid, technical preferences, brand voice, ethical
  lines).
- **Hold the operating policy** — the leash: how much autonomy the company has,
  which actions always require the CEO, the budget cap, the limit on how many
  product lines run at once, how often the company should think, and where new
  repos get created. These are levers, not constants buried in code.
- **Be the single source of truth agents orient to** — the active direction is
  present in every agent's working context, so all work is goal-aware rather than
  blind. An agent should always be able to answer "what are we trying to do, and
  within what limits."
- **Treat a change of goals as a real event** — when the CEO revises direction,
  the company notices and re-orients; a goal edit is consequential, not silent.
- **Expose its derived state read-only** — progress toward each objective, how
  much in-flight work actually maps to a goal (coverage), work or spend that maps
  to none (drift), and spend against budget. The CEO sets the top half; the
  company reports the bottom half.
- **Be editable through the CEO's interfaces** — the Panel and the Secretary —
  never by hand-editing code or config files.

## What good looks like

- The CEO can state the company's direction and limits once, in plain language,
  and see it reflected in what the company prioritizes.
- Changing a goal visibly shifts what the company does next.
- Any agent, at any level, is demonstrably acting in service of a stated
  objective — or the misalignment is visible as drift.
- A newcomer (human or agent) reads the Goals and understands the company.

## Boundaries

- It **describes** direction; it does not **generate** work — that is the
  work-generation engine (Phase 5). Goals is read by that engine, not it.
- It **declares** guardrails (budget, caps, gate list); enforcement of those
  lives with the phases that act (provisioning, the autonomous loop).
- Its metrics are **proxy** by nature — real revenue and users require external
  launches that stay gated. Goals measures what a local company can measure.

## Depends on

The existing task/agent system (to inject direction into). Nothing else — this is
the foundation the rest stand on.

## Open questions

- The vocabulary of metrics, and how "goal-coverage" is computed from in-flight
  work.
- The lifecycle of an objective (active → achieved → retired) and how the company
  decides an objective is met.
- Whether Direction and Operating Policy are one editable surface or two related
  ones (they are edited together but are different kinds of thing).
