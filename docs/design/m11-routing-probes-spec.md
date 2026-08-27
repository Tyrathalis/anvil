# M11-routing ceiling probes — tutor/fetch targets + resolution-effect payments (ADJUDICATED 2026-08-26)

*Design-round obligation 6 ([m10-plan.md](m10-plan.md)), funded by name
at the 2026-08-25 scoping discussion: two session-scale ceiling
measurements riding the M10 design round, ROUTING M11, never gating
M10's build. The ADR-0073 measure-the-ceiling genre on the ADR-0053
forced-branch machinery; both claims per the standing rule (per-window
value AND gate-scale = rate × per-window). The effect-payment probe IS
the measured argument ADR-0077 requires before that item can be
re-deferred a second time.*

## Shared discipline (both probes)

- **Population: uniform over mined windows** (the ADR-0075 lesson —
  mining defines the surface, never value-filters it; any
  value-selected stratum is exploratory and winner's-curse-priced).
- **Store: `m10-ceiling-census-20260825-212414`** (era iter-019,
  boundary bundle) for the mining census; rollout populations
  re-derived at the same seeds. Rebaselinearm stores as the fallback
  volume source if window rates are too thin (recorded either way).
- **Rolls: K=8 with the structural select/score split** (select on
  rolls 0–3, score on 4–7 — the sched_pins precedent; best-arm
  ceilings inflate without it).
- **Read: per-window paired Δwr at game end** (forced-best vs natural
  reference), clustered by game; gate-scale = measured window rate ×
  per-window delta. Divergence/void caps pre-registered per arm
  (exhaustion precedent).
- **Routing rule (pinned pre-data at each probe's launch):** gate-scale
  ceiling ≥ the M10 funding threshold (the ADR-0078 pinned ~2.25pp/game
  scale) ⇒ the item schedules into M11 scoping by name; below ⇒
  re-deferred WITH the number attached (ADR-0077's condition
  satisfied either way).
- **Mining rung first, forcing rung second:** each probe opens with a
  CPU-only store census (window rate, candidate-set sizes, seat/turn
  distribution) — the rate half of the gate-scale claim and the
  arm-budget input — before any engine work runs.

## Probe T — tutor/fetch-target ceiling (§3d′ family 2)

- **Window definition:** own-seat `chooseSingleEntityForEffect` AND
  `chooseSingleCardForZoneChange` decisions (SELECT_ONE shape) whose
  candidate set is a library/multi-zone search (tutor/fetch class),
  candidate count ≥ 2. Multi-entity search variants
  (`chooseEntitiesForEffect` 0.70/g, `chooseCardsForEffect` 0.43/g)
  counted in the census, forced only if their rate is material
  (recorded fork).
- **Measured raw rates (census.jsonl sweep, 500 games, 2026-08-26):**
  `chooseSingleEntityForEffect` 5.87/g, `chooseSingleCardForZoneChange`
  5.79/g — before the library-search/candidate-count filter, which the
  mining rung applies. The class is 20–50× the M9 payment window rate
  pre-filter; the surface is live at census resolution.
- **Arms:** force each distinct candidate target, capped at the top-k
  by a cheap static order (k pinned at launch from the census
  candidate-size distribution; full enumeration when ≤ k) + the
  natural arm (the AI's unforced pick) as the paired reference.
- **Read:** best-forced vs natural Δwr per window (select/score
  split); heuristic-regret = natural vs best among forced arms.
- **Engine delta owed:** `-forcechoice` — force a designated
  SELECT_ONE outcome at a (seed, turn, window-ordinal) key; the third
  member of the `-forcebranch`/`-forceschedule` family, same
  labels-JSONL output contract.

## Probe P — resolution-effect payments ceiling

- **Window definition:** `payManaCost` windows with `effect=true`
  (resolution-time pay-or-suffer; the census stream carries the flag).
  **Measured: 50.12/g raw (25,061 events / 500 games, census.jsonl
  sweep 2026-08-26)** — the plan's ~54/g confirmed in the fresh era.
  The mining rung splits this into the pay-or-suffer subset (decline
  legal) vs mandatory payments; only the former is forced.
- **Arms:** force-PAY vs force-DECLINE at each mined window (binary in
  the pay-or-suffer class; windows with a payment-choice interior are
  counted in the census and routed to the directed-payment machinery
  only if their rate is material — recorded fork). Natural choice
  recorded ⇒ regret read (value lost by the AI's actual pay/decline
  policy) rides free.
- **Read:** pay−decline Δwr per window + natural-choice regret;
  gate-scale by the re-measured rate.
- **Engine delta owed:** force pay/decline at effect-payment windows —
  a knob on the existing payment executor path (float-then-apply
  machinery already brackets the window; the force is a decision
  override, not a new payment path).

## Explicitly out

- Any training wiring for either surface (routing probes only).
- Value-model-guided target selection for tutors (that is the M11
  build question these numbers fund or kill).
- Effect payments with nontrivial payment interiors beyond the
  census count (recorded, not forced, this round).

## Pinned at each launch, pre-data

k (probe T), K-roll caps and void caps, the routing threshold
restated numerically, seed bases, and the mining-census frame — the
sched_pins pattern: an executable pins module per probe, prose
mirrored here.

## Adjudication record (user, 2026-08-26 — all four on the recorded leans)

1. **Probe T windows: both SELECT_ONE classes**
   (`chooseSingleEntityForEffect` + `chooseSingleCardForZoneChange`),
   library/multi-zone-search filtered, ≥2 candidates; multi-entity
   variants census-counted, forced only if material.
2. **Probe P forcing scope: decline-legal windows only** (pay-or-suffer
   proper); mandatory payments census-counted for context.
3. **Routing threshold PINNED: gate-scale ceiling ≥ the ADR-0078
   funding-threshold scale (≈2.25pp/game)** ⇒ schedule into M11;
   below ⇒ re-defer with the number (ADR-0077's condition satisfied
   either way). Restated numerically in each probe's pins module at
   launch.
4. **Engine-delta sequencing: after the v2 target probe read** — one
   Java session builds `-forcechoice` + the pay/decline override
   together (one fork touch); the CPU mining rungs run in between.
