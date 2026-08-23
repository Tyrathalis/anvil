# ADR-0070: Chronicle needs an effort→reward sink; the kitchen-table stretch is promoted

- **Date:** 2026-08-22
- **Status:** accepted
- **Design-doc anchor:** [collection-mode-sketch.md](../design/collection-mode-sketch.md)
  "MVP slice spec v0" / "Structural design v0" layers 2–3;
  [chronicle-mvp-plan.md](../design/chronicle-mvp-plan.md) Scope + Deliverables

## Context

D5 (dogfood) opened on 2026-08-22 with the author's first real phone-based
round on the daily loop. The reveal-scene findings are mechanical and handled
separately (see the plan's D3 section). This ADR records the one finding that
is a **design** result rather than a bug.

The author's report, in their words: the pack opening "isn't quite drawing me
to keep opening packs every day when there's truly nothing to do with the cards
but look at them," and — on follow-up — what is missing is **"something that
works as a time sink, so if you feel like putting more time into the experience
you get rewarded for it."**

This is the MVP's known hole arriving on schedule. MVP slice spec v0 cut the
battler, tournaments and the market explicitly, and made kitchen-table play
(deck editor + ownership-legality) the **stretch** — "build only if the slice
lands early." The slice landed on time and the stretch was never built, so the
shipped loop is: collect ration → open packs → sort binder → sell dupes →
open packs. Every channel in it is a *grant*. The only income is the allowance
stipend ($10 per played week against $2.45 packs), pack EV is negative by
invariant, and the buylist pays out less than the packs cost by construction.
There is no action anywhere in the mode whose reward scales with how much of
yourself you put into it.

The sketch stages that scaling as **layer 2 (idle battler)** and **layer 3
(deckbuilder)**, behind layer 4's market — i.e. two stages out. That ordering
was chosen so the timeline teaches the layers in the order Magic itself grew
them. It survives this ADR: what is being promoted is not the battler.

## Decision

1. **A new requirement is pinned for Chronicle, above the MVP/stage line:**
   the mode must contain at least one channel where **invested time converts
   into progress**. Grants on a daily timer are not such a channel. This is
   now a first-class property of the design, not a stage-2 feature — the
   dogfood measured its absence as the thing that ends the daily habit.

2. **The kitchen-table stretch is promoted out of "stretch" into a scoped
   deliverable, D6** (see the plan): deck editor wiring with
   ownership-legality, play against the AI, and a **purse** on the result.
   Deck editor, AI and match runner all already exist in Forge; this is
   wiring plus an economy line, not new machinery.

3. **Priority: D6 is the highest-value remaining Chronicle work**, ahead of
   the D5 numbers pass. It is explicitly *not* required to be the immediate
   next commit — the reveal-scene round in flight finishes first (author's
   call: "we don't necessarily need to make it the immediate thing after the
   improved pack opening animation, but... I want it to be a higher
   priority").

4. **The numbers pass moves behind D6.** Ration size, stipend cadence and the
   MSRP/buylist tables are all currently at their seed defaults, and a purse
   changes what every one of those numbers should be. Tuning them first would
   be tuning an economy that is about to gain an income source.

5. **Period fidelity is preserved, and constrains the purse.** Kitchen-table
   play in 1993–94 is period-correct — it is the *venues, organized play and
   tournament income* that would be anachronistic, and those stay out. The
   purse therefore needs a flavor answer that fits a kitchen table rather than
   a prize wall; that answer is open (see Consequences).

## Consequences

- **MVP scope expands by one deliverable.** The visibility flip (D5 exit) now
  gates on D6 as well, since the loop being dogfooded changes shape. The
  two-week dogfood clock effectively restarts when D6 lands.
- **The pack-EV invariant is unaffected.** Packs stay EV-negative; the purse is
  a separate income channel, exactly as the allowance stipend is. But the
  Ante pack-EV ledger's framing ("what did chance take and give") now has a
  second income source to sit beside, and the economy's total inflow is no
  longer a fixed weekly constant — the D5 numbers pass has to be re-derived
  against a variable-income loop.
- **Open: the purse's flavor.** A kitchen-table game paying cash is the easy
  implementation and the weakest fiction. Candidates to settle at D6 design
  time: ante (period-authentic, in the rules of the era, and it is what the
  Ante module is *named* for — but it risks the collection as a stake, which
  cuts against the collection chase); a trade rather than cash; or simply
  reflavoring the allowance as chores-and-play. Not decided here.
- **Open: how deck legality reads the collection.** Ownership-legality over the
  printing×finish inventory is the stated shape; whether a deck consumes or
  merely references owned copies (and how duplicates across printings count)
  is a D6 design question.
- **Layer ordering in the sketch is unchanged.** The battler, venues,
  tournaments and the market keep their stage-2/3 positions. D6 is the
  cheap kitchen-table instantiation of the new effort→reward requirement, not
  an early draw-down of layer 2.
- **The requirement outlives its first implementation.** If D6's purse turns
  out not to satisfy the pin, the pin stands and the next candidate gets
  scoped against it — the finding is "grants alone do not hold the habit,"
  which no single feature can retire.
