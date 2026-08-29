# Standing rules

One line per rule, grouped by when you need it, each linked to the ADR
that born it. This is the consolidated register — milestone bullets in
CLAUDE.md no longer enumerate rules, they point here. **Read the
relevant section before designing any run, gate, instrument, or
curation cycle.** (The seven design invariants stay in CLAUDE.md; this
file is the operational layer under them.)

Maintenance: when an ADR births a rule, add it here in the same commit
batch; when a rule is superseded, strike it with a pointer, never
silently delete.

## Gates, reads, and statistics

- Gate a capability on a **discrimination statistic**, never an
  accuracy count; a day-zero-0-correct sub-population is a gate defect
  ([ADR-0069](decisions/ADR-0069-d4-read-adjudication.md)).
- **Measure the ceiling before building the learner**
  ([ADR-0073](decisions/ADR-0073-m9-ceiling-measurement.md)).
- **Per-window value and gate-scale value are distinct claims** — a
  ceiling statement carries both ([ADR-0073](decisions/ADR-0073-m9-ceiling-measurement.md)).
- A re-cert threshold on a selected population must price
  **winner's-curse regression**, not only drift
  ([ADR-0073](decisions/ADR-0073-m9-ceiling-measurement.md)).
- **Read every pre-registered signal** before closing a run's verdict
  ([ADR-0069](decisions/ADR-0069-d4-read-adjudication.md)).
- A recipe pin that removes a condition must be **re-checked against
  every pre-registered readout**; a control restores the CONDITION,
  not the asset ([ADR-0069](decisions/ADR-0069-d4-read-adjudication.md)/[ADR-0072](decisions/ADR-0072-d4-control-run-veto-collapse-falsified.md)).
- An evalset's **certification horizon is part of its type** — never
  let "certified" stand unqualified in a strength argument
  ([ADR-0072](decisions/ADR-0072-d4-control-run-veto-collapse-falsified.md)).
- **Fixed-subset arms reads are ONE observation, not N**
  ([ADR-0058](decisions/ADR-0058-m7-closeout.md)); ~1.5σ small-N arms
  teases are a confirmed recurring artifact — three instances on file.
- **Single-seed-set reads at ~1pp are inconclusive** — the combined
  paired read is the standard ([ADR-0037](decisions/ADR-0037-m5-closeout.md));
  fresh-seed paired confirmation is the marginal-t tiebreaker
  ([ADR-0033](decisions/ADR-0033-m4-closeout.md)).
- When a gate goes flat while instruments improve, **audit the signal
  path before reaching for the next lever**
  ([ADR-0049](decisions/ADR-0049-flat-cycle-audit.md)).
- Battery findings are **exploratory only** — verdicts stay
  pre-registered ([run-analysis-protocol](design/run-analysis-protocol.md)).
- **Conditioning-surface flip gates read the content channel** (its
  true-zero floor); presence floors are banked and SUBTRACTED, never
  absorbed into absolute bars — v1 absolute thresholds do not transfer
  to surfaces whose tokens perturb attention by presence
  ([ADR-0084](decisions/ADR-0084-m10-probe-preflight.md)).

## Training-loop design

- **Clips at birth** for engineered aggregates AND loss terms
  ([ADR-0050](decisions/ADR-0050-m6-closeout.md)/[ADR-0056](decisions/ADR-0056-run14-seq-divergence.md)).
- Auto-calibrated weights get their invariant **instrumented, guarded,
  and recalibrated at the cadence it varies**
  ([ADR-0057](decisions/ADR-0057-run15-share-drift.md)) — per-iteration
  w recalibration is the default.
- **An aux-target's SHAPE is a behavioral prior** — what the latent
  predicts is what the policy is nudged to enact; target design is
  behavior design ([ADR-0076](decisions/ADR-0076-d6-probe-read.md)).
- Price a conditioning channel's lr by its **gradient DENSITY, not its
  init** ([ADR-0076](decisions/ADR-0076-d6-probe-read.md)); the
  starved-param arithmetic ([ADR-0069](decisions/ADR-0069-d4-read-adjudication.md))
  applies to heads fed by rare windows.
- **Falling reliance + compounding behavior = absorption**, not disuse
  — read the flip metric jointly with the behavioral series
  ([ADR-0076](decisions/ADR-0076-d6-probe-read.md)).
- A guard-halt relaunch after a **recipe change must clear the
  rejected phase's artifacts** (archive, don't delete) — phase-reuse is
  for crashes, not amendments ([ADR-0076](decisions/ADR-0076-d6-probe-read.md)).
- **Probe-first discipline**: a D4-shape short run with a
  pre-registered kill signal before any promotion-scale run (M9
  practice, priced as intended at [ADR-0076](decisions/ADR-0076-d6-probe-read.md)).
- The standing veto account: under auto-payment, **probing-via-veto IS
  optimal play** — the veto channel is the model's only affordability
  oracle; deterrence-family levers are CLOSED
  ([ADR-0062](decisions/ADR-0062-m8-closeout.md), falsification
  completed at [ADR-0072](decisions/ADR-0072-d4-control-run-veto-collapse-falsified.md)).

## Curation, drills, and the critic

- **Drill mainlines never enter training ingest**; curation regenerates
  from the current ckpt-of-record's own losses every cycle;
  selection/evalset versions are ckpt-era-scoped
  ([ADR-0033](decisions/ADR-0033-m4-closeout.md)/[ADR-0031](decisions/ADR-0031-a2-resolution.md)).
- **The migration read gatekeeps cycle pricing**
  (`scripts/migration_read.py`, [ADR-0037](decisions/ADR-0037-m5-closeout.md)).
- **Critic ordering is not evidence in loss-adjacent populations** —
  ranking comes from rollouts ([ADR-0036](decisions/ADR-0036-d3-critic-calibration.md));
  critic-classified fractions are instrument-limited, rollout maps
  authoritative ([ADR-0037](decisions/ADR-0037-m5-closeout.md)).
- **Isotonic maps are era-scoped assets**; the value-audit label set
  grows with every map/sweep ([ADR-0036](decisions/ADR-0036-d3-critic-calibration.md)).
- **Probe on `[STATE]`, never the trained head**; inner-val pools are
  pinned ([ADR-0050](decisions/ADR-0050-m6-closeout.md)).
- Mid-campaign checkpoints **sweep the two leading Ns**
  ([ADR-0050](decisions/ADR-0050-m6-closeout.md)).
- Check whether candidate curation stock is **gate-seeded** before
  using it (`m9-rebaselinearm` shares `final_read.py`'s seed base —
  [ADR-0068](decisions/ADR-0068-m9-boundary-bundle.md)).
- **Curriculum composition (behind/ahead balance) is a first-class
  lever** ([ADR-0033](decisions/ADR-0033-m4-closeout.md)).
- **Veto-elevated run stores never enter a training mixture**:
  run14/15/16 ([ADR-0058](decisions/ADR-0058-m7-closeout.md)),
  run18/19/20 ([ADR-0077](decisions/ADR-0077-m9-closeout.md)) —
  permanent.

## Engine, fork, and data hygiene

- **Bridged JVMs leak one game graph per game unless AiCache is cleared
  between games — chunk recycling is load-bearing**; never run a
  bridged JVM unbounded without one or the other (upstream
  `AiCache.dataMap` clears only on the heuristic AI priority path
  bridged seats never take; heap-dump-proven at the M10 sweep OOM;
  within-game clears = a boundary-event candidate
  ([ADR-0078](decisions/ADR-0078-m10-ceiling-measurement.md))).
- **Engine upgrades are dataset-boundary events**; the
  behavior-identical exemption is proven empirically (same seeds →
  identical forkcheck trace hashes), never argued
  ([ADR-0025](decisions/ADR-0025-d4-rebase-closeout.md)); `forge
  forkcheck` at the BC certification ckpt is the standing bump gate.
- **Every pre-boundary number is old-scale** — never compare winrates
  across eras; cross-era gen_s comparisons only at identical chunking
  ([ADR-0025](decisions/ADR-0025-d4-rebase-closeout.md)/[ADR-0033](decisions/ADR-0033-m4-closeout.md)).
- An enumerator's **unit of exclusivity must be the unit the executor
  consumes** ([ADR-0066](decisions/ADR-0066-certify-salvage-host-exclusivity.md));
  corollary: a certified "best" over rolled-out arms is a **CLASS
  statement** — any consumer collapsing it to one index must show the
  collapse is behavior-neutral (the "unreachable" evalset positives
  were exact-index scoring on margin-tied arms,
  [ADR-0082](decisions/ADR-0082-payment-evalset-repair.md)).
- **`sa_vocab` is pinned — never regenerate in place**
  ([ADR-0012](decisions/ADR-0012-d2-d3-closeout.md)); obs sv eras never
  mix (strict reader gate, [ADR-0068](decisions/ADR-0068-m9-boundary-bundle.md)).
- **Never read a bridge answer field without checking `fallback`
  first**; eval runs keep census+obs on; zero-error validation is the
  corpus-launch gate ([ADR-0009](decisions/ADR-0009-m1-closeout.md)).
- **BC is finished as a strength program** (the pre-RL scope rule,
  [ADR-0012](decisions/ADR-0012-d2-d3-closeout.md)).
- Milestone close includes the **stale-data deletion pass** (inventory
  → reference-grep → kill list → user sign-off); drills.jsonl dirs,
  ckpts of record, selection/evalset assets, baseline arm stores, and
  Ante certs are unconditional keeps (CLAUDE.md workflow section).
- Standing hazards: the playable build shares Forge's user deck store
  with research (`launch --pool` hash-gates it); **never check out
  `playable` in the research worktree**; pool selection rides
  `data/pool/CURRENT`, never mtime.

## Scoping and routing

- **Every deferral is routed BY NAME** at the next scoping session and
  the closeout ADR — scheduled, or re-deferred with a recorded reason;
  silent loss is not an outcome (the payment-queue rule, m9-plan;
  executed at [ADR-0077](decisions/ADR-0077-m9-closeout.md)).
- **Capabilities over heuristic fallback** (user default): keep/add
  model capabilities unless dramatically weaker — the
  compounding-surface hypothesis (plan × payment).
- **Promote on cleared gate** (user default) unless the run itself is
  suspect.
- Content breadth scales in set-sized dataset-boundary chunks after
  core features ([ADR-0018](decisions/ADR-0018-ruleset-scope-clarification.md)
  recipe-first).
