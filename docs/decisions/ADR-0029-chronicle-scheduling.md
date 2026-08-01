# ADR-0029: Chronicle scheduled — playable-branch side stream, MVP slice v0

- **Date:** 2026-07-31
- **Status:** accepted
- **Design-doc anchor:** new ([collection-mode-sketch.md](../design/collection-mode-sketch.md))

## Context

Chronicle has been a parked concept since 2026-07-18, grown through design
rounds (structural v0 07-20, the daily-gacha/Pocket round 07-31) to the point
where the sketch's own devlog verdict was "the MVP slice spec is buildable as
written." The sketch's promotion rule: real plan doc + ADR if/when scheduled.
This session the user scheduled it: implementation planning began, with the
mode to be published into the `playable` branch (the friends' QoL/distribution
build) and eventual **upstreaming** as the long-range goal (a prompt typo —
"streaming" — clarified to mean exactly this; the fork-first/re-cut strategy
already pinned 07-31 is the vehicle).

An implementer's read of the MVP spec surfaced one genuine design gap (the MVP
has no income source: battler out, pack-cracking instant-EV-negative by
invariant, buylist only recycles — currency strictly drains) and several
under-specified implementation-facing points (day-tick trigger semantics, seed
integrity vs save-scumming, prestige-readiness of the save schema).

## Decision

**Chronicle is promoted from parked concept to a scheduled build stream.**

- **Stream identity:** playable-branch side stream, sibling to the QoL/fork
  work; NOT on the M4 research path. M4 keeps the research hours.
- **Plan of record:** [chronicle-mvp-plan.md](../design/chronicle-mvp-plan.md)
  (architecture, staging D0–D5, gates). The sketch stays the canonical design
  record.
- **Session pins (user):** MVP income = allowance stipend (the gap's fix,
  period-flavored, retires when tournament income arrives); Android packaging
  spike parallel-early; Chronicle hidden behind a pref until the author's
  two-week dogfood gate passes; day tick fires on ration collection (≤1 per
  real calendar day, local time + early-morning grace); all daily randomness
  deterministic from (run seed, day index, domain) with sealed-item contents
  committed at acquisition — no reroll by restart; save schema carries run-id +
  separate meta blob from day one (prestige-proofing).
- **Architecture (from the plan):** headless services in
  `forge-gui/.../gamemodes/chronicle/` (Quest precedent; headlessness enforced
  by module structure), screens in `forge-gui-mobile`, data in
  `forge-gui/res/chronicle/`, tests in the desktop TestNG tree (mobile stays
  test-infra-free), Adventure `SaveFileData` persistence pattern.

## Consequences

- The playable-fork hours budget now carries Chronicle; the QoL track's
  remaining residue (T2) and Chronicle compete there explicitly.
- First code deliverables: D1 headless core (+ simulated-fortnight gate) and
  the D4 Android spike in parallel — Android packaging joins the pipeline
  because the dogfood gate is phone-based.
- The seed-integrity and stipend decisions are design-record material and have
  been folded back into the sketch as a dated addendum.
- The courtesy Discord concept-float is deliberately timed at the D5
  visibility flip, not before code.
