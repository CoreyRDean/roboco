# Phase 6 — The Cockpit

*Descriptive spec. See [INTENT.md](../INTENT.md) §4.*

## What this is

The Panel matured into a true CEO **cockpit** — the visual surface where the CEO
watches the company and acts on the few things that need them. Paired with the
Secretary (the conversational surface), it completes the CEO's interface into a
running, autonomous company.

## Why it matters

An autonomous company is only as governable as it is legible. If the CEO can't
tell at a glance whether the business is winning, what's happening, and what needs
them, then "walk away and let it run" becomes "fly blind." The cockpit makes a
self-running company understandable and steerable in a minute, not an
investigation.

## What it must do

- **Answer three questions at a glance** — *Is the business winning? What is
  happening right now? What needs me?* Everything on the surface earns its place
  by serving one of those.
- **Show performance against goals** — progress on each objective, and the proxy
  metrics a local company can honestly measure (products shipped, quality,
  velocity, goal-coverage) — alongside spend versus budget and active products
  versus the cap.
- **Make the action queue the focal point** — the short list of gated decisions
  waiting on the human, each with enough context to decide. This is the thing the
  CEO clears; it should be impossible to miss (the lesson already learned: a gate
  buried on a detail page is a gate that never gets seen).
- **Surface drift and stalls visibly** — work or spend not tied to a goal, and
  work that has stranded, show up as signals rather than hiding.
- **Support "watch and clear" as the default mode** — the calm state a CEO lives
  in, dropping into the Secretary only to steer.

## What good looks like

- A CEO understands company health and acts on what needs them within a minute,
  without digging through tasks or logs.
- Nothing waiting on the CEO is ever invisible.
- The honest boundary is respected on screen: performance is shown as proxy
  metrics until real external launches are greenlit — the cockpit doesn't pretend
  to measure revenue that isn't there.

## Boundaries

- It is **legibility, not autonomy** — it shows and routes; it does not decide.
  New behavior belongs to the engine, not the dashboard.
- It shows **proxy** outcomes by design; real-world outcomes live behind the
  gated, external actions the CEO approves.
- It is the *watch* surface; *conversation* is the Secretary's job. The two
  complement, they don't duplicate.

## Depends on

Goals (Phase 1) for the metrics and objectives to render; the work-generation
engine (Phase 5) for the activity to show; the action queue (already built,
surfaced correctly) as its centerpiece.

## Open questions

- Which metrics lead the view, and how goal-coverage and drift are best
  represented so they're glanceable, not noisy.
- How much history/trend to show versus the live now.
- Whether anything beyond the queue deserves to actively alert the CEO (push)
  rather than wait to be seen (pull).
