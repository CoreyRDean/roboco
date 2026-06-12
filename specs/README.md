# RoboCo — Phase Specs

Descriptive specs for the phases on the roadmap in [`INTENT.md`](../INTENT.md) §12.

**These are descriptive, not prescriptive.** Each spec says *what* a phase is,
what it must do, what good looks like, and where its boundaries are — the intent
a builder must satisfy. None of them say *how* to build it: no data schemas, no
endpoints, no file layouts, no step-by-step. Implementation plans derive from
these later, and may choose any mechanism that honors the spec.

Read [`INTENT.md`](../INTENT.md) first — it is the north star these phases serve.
The throughline: **the human supplies direction and judgment; the company
supplies everything else.** The delivery engine (build → QA → docs → merge)
already works and stays untouched; these phases add the layer that decides what
to feed it and the surfaces the CEO uses to steer.

| # | Phase | One line |
|---|-------|----------|
| 1 | [Business Goals](01-business-goals.md) | The CEO-set charter every agent reads and the company pursues. |
| 2 | [Web & Market Research](02-web-research.md) | Let the company see the real world, with citations. |
| 3 | [The Secretary](03-secretary.md) | The CEO's conversational chief-of-staff — the two-way interface. |
| 4 | [Pitch → Approve → Provision](04-pitch-approve-provision.md) | The company invents a product, the CEO says yes, it stands itself up. |
| 5 | [Autonomous Cadence & Caps](05-autonomous-cadence.md) | The work-generation engine runs on its own, within bounds. |
| 6 | [The Cockpit](06-cockpit.md) | The Panel matured into a watch-and-act surface. |

Sequencing rationale (from INTENT §12): prove pitch *quality* with the human in
the loop before automating the trigger; provision only what's approved; never let
an autonomous loop mint products before the CEO has seen the quality.
