# ADR-0068: The M9 boundary event — one bundle

- **Date:** 2026-08-21 (bundle landed; certification + re-baseline reads pending — see Status)
- **Status:** accepted (reads IN FLIGHT: forkcheck + m9-rebaseline final_read fill §Reads below)
- **Design-doc anchor:** m9-plan "Boundary discipline: ONE boundary event" + done-when 3

## Context

M9's design pinned a single dataset-boundary event carrying every queued
engine-side change, held until the §3c payment surface was ready. The D4
gate session (2026-08-21) added the evalset revalidation pass as the fifth
boundary obligation. This ADR records what the bundle landed, the explicit
verdict on each queued item, and the era-scoping consequences.

## Decision — the bundle contents (fork `master`, rebased tip)

1. **Upstream rebase.** Fork master rebased onto upstream tip `23c3d2a85d`
   (2026-08-22; last ~15 upstream commits are UI/adventure work — no fresh
   AI-behavior churn near the pin, per the ADR-0025 pin-choice discipline).
   64 fork-local commits replayed, zero conflict stops; the two Player.java
   fork fixes (monarch ternary, mapEffectCard zone-membership) verified
   present post-rebase. Pre-rebase tip preserved as branch
   `pre-rebase-20260821`. 108 upstream commits absorbed.
2. **§3c payment surface merged.** `m9-payment-surface` tip `116476eebb`
   (14 commits: enumerator, goal options, directed executor, ADR-0066/0067
   admissibility fixes, wiring, telemetry, certify + observe modes) was a
   clean fast-forward into master pre-rebase. The branch's isolation rule
   (never touches research master pre-boundary) is discharged.
3. **Fork-index store-namespace fix (the run17 iter-2 collision).**
   `-forkns <n>`: synthetic fork ids become
   `FORK_G_BASE + ns*1e9 + (gameIdx*100+fp)*100+r`; the grindstone planner
   assigns ns per source store (sorted ordinal) and records it in the drill
   manifest; the orchestrator threads `--fork-ns`; offset overflow into the
   next namespace slice is a loud failure. ns=0 reproduces the old encoding.
   The id stays a pure join key. The M8 era-clean mitigations (cross-store
   g-unique selection dedupe + the loud MultiStore FATAL) stay as belt.
4. **Obs schema v2** (`Obs.SCHEMA_VERSION = 2` / Python
   `OBS_SCHEMA_VERSION = 2`; the strict reader equality check IS the era
   gate):
   - **Entity choice-state kv** (`"cho"`: col/typ/typ2/num/pl/ent/nam),
     emitted in public zones when any declared choice exists. VIEW-sourced,
     not Card-sourced: secret choices (`setSecretChosenType` etc.) reach the
     CardView only on reveal, so the view is exactly the table-public
     knowledge and no per-field visibility gating is needed
     (`ObsChoiceStateTest` pins the no-leak property). **Recorded
     residuals:** direction/even-odd/mode choices are not emitted; chosen
     types and named cards are featurized only via dedup separation (text
     channel), not numeric columns.
   - **Featurized slice:** ENTITY_FEATURES +7 (chosen-color WUBRG bits,
     cho_num, has_cho), appended so `load_compat`'s ent_proj zero-pad loads
     pre-boundary checkpoints byte-identically.
   - The bump also blesses the additive payment-window kv (goal-shaped
     labels) that had ridden sv=1 as additive-only since rung 2.
   - Live check: the 60-game bundle-jar pilot carried choice-state on
     3,422 decision windows — the family is common, not exotic.
5. **Multi-format model-side enablement.** Format one-hot appended to
   GLOBAL_FEATURES, driven by the new vocab `formats` registry (unknown
   format = loud VocabError; registry/column lockstep asserted at Vocab
   init). `load_compat` gained a state_proj INSERT zero-pad (the fmt
   columns sit mid-input — globals precede flattened players), asserted
   byte-identical against the real d5 checkpoint. A NEW format appends its
   column + registry entry at its own dataset-boundary event (ADR-0018
   chunking); the transfer probe stays pre-registered for when breadth
   opens. No pool/content growth rode the bundle.
6. **2-arm campaign trim: RETIRED explicitly.** The forced-seq campaign is
   opt-in (`--seq-n`, absent from the standing recipe); the act−hold
   formulation it served was retired at ADR-0058/0062; the M8 single-arm
   flag (`-seqarms nat`) already covers the only chartered future use (the
   natural-timing formulation needs the natural arm alone). Nobody pays the
   ~0.5h/iter the trim would have saved. No code landed; the queue item is
   closed with this record.
7. **Instrument fixes in the ADR-0059 hazard genre:** harness `_find_jar`
   now newest-mtime + multi-jar warning (was alphabetical — same class as
   the run_forkcheck stale-jar pick); run.json `obs_schema` now pins
   `OBS_SCHEMA_VERSION` (was hardcoded 1).

## Era-scoping consequences

- **Never mix sv=1 and sv=2 stores in any reader/join** — enforced by the
  strict sv check, not convention.
- Pre-boundary selection / evalset / isotonic assets are era-closed;
  regeneration follows the standing rules (selection from the
  ckpt-of-record's own losses on new-era stores).
- Era-scoped test fixtures: the parity/sampling test modules skip loudly on
  pre-boundary stores (`tests/conftest.py era_store`); the pilot fixture
  store is regenerated on the bundle jar (`pilotv2`), the mu-covered
  sampled-store fixture (test_critic_loop) repoints at the first D4-era
  sampled store (recorded gap until then).
- The pre-boundary gate number **0.5373 ± 0.0112** is reference-only; the
  M9 gate re-pins on the m9-rebaseline read.
- `data/forkcheck/m8d1-proof` jars prune to results+meta once the
  m9-boundary forkcheck supersedes them (ADR-0060 note).

## Reads (PENDING — each line fills in when its run completes; no number
## below exists yet)

- **Forkcheck certification (`run-20260821-m9boundary`, 500 games, default
  mode): DONE 2026-08-21.** **450 clean / 50 divergence = 10.0%**, statics
  0, crashes 0 — at/slightly below the ADR-0059 corrected pre-boundary
  characterization (11.2–11.4%): the rebase did not degrade copy-state
  fidelity. The 50 divergence rows are the copy-state forensics substrate
  (queued item, not boundary-gating; the FIXED_HASH same-sequence triplet
  on this jar is its next step, daytime run).
- **Re-baseline (`m9-rebaseline` final_read, iter-019 via load_compat on
  the bundle jar, ~2,000 paired games):** [PENDING — the corrected read
  RE-PINS THE M9 GATE NUMBER; 0.5373 ± 0.0112 is reference-only. Riders:
  hygiene census, battery anomalies, seed-half consistency, the
  never-cast/never-seen-vs-pool-census check (run-analysis-protocol
  boundary row).]
- **Evalset revalidation pass (`run-20260821-revalidation`, observe lanes
  on the bundle jar): DONE 2026-08-21.** 293 jobs → 278 scored.
  **option_mismatch = the SAME 3 jobs as day-zero (9/119/138, b1/b2) — no
  NEW enumeration drift: the rebase did not move payment enumeration on
  any surviving window.** NEW exclusion class: **12 window misses (4.1%;
  4 positive, 8 auto-correct)** — same-seed replays that no longer reach a
  bridged consequential window on the rebased engine (the known replay-
  drift class, dose above the ~1–2% wall-clock prior — plausibly upstream
  game-logic changes shifting heuristic lines; miss jobs recorded in the
  score rows, excluded not re-labeled). **Compat prediction CONFIRMED
  EXACTLY: all 278 windows scored in both eras produce IDENTICAL argmax
  picks (0 flips)** — the zero-pads are behavior-clean in production, not
  just in unit tests. **Re-banked post-boundary day-zero baselines
  (`score-dayzero-iter019-v2.jsonl`): positive 2/64 (3.1%), auto-correct
  196/214 (91.6%), argmax deviation 24/278 (8.6%)** — the same decisions
  as the pre-boundary bank; percentage shifts are purely denominator.
  Shape floors on surviving positives: bp 12 / ch 25 / phy 13 / wc 14 —
  **all ≥ 10 ✓**. Gate arithmetic carries to the surviving population:
  FUND = ≥7/64 positive (≥5 net over day-zero 2/64) with auto-correct
  ≥85% (≥182/214) same-iteration; the D4 read notes the denominator.

## Consequences

- D4 launches on this era: baselines = the re-banked day-zero drill scores
  + live `pay_deviation` at the run's own iter-0; gate per the D4 gate
  session pins (FUND ≥7/68 positive with ≥85% auto-correct; CLEAN NEGATIVE
  <2% deviation with ≤4/68).
- Copy-state forensics starts from the new forkcheck's divergence rows
  under the ADR-0059-corrected instrument (same-sequence replication runs;
  FIXED_HASH triplet queued as its substrate — post-boundary diagnostic,
  never reopens the boundary).
- The payment-completion queue is untouched by the bundle (items 2–5
  remain; item 5's enumerator freeze now binds against the NEW era's
  certification jar).
