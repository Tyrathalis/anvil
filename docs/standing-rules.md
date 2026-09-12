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

- **A conditioning surface's ceiling funds only the execution regime it
  was measured in** — the M10 ceiling (+13.5pp) was measured under
  binding `-forceschedule` execution and six probes tried to earn it on
  an advisory surface ([ADR-0094](decisions/ADR-0094-m10-reset.md)).
- **A probe's PRIMARY read is a strength read on the funded stratum with
  the ceiling's own paired instrument; competency proxies are
  exploratory** — six probes read proxies that measured the wrong thing
  (presence, lumped counters, natural-line inflation) while the prize
  sat unmeasured; a day-zero read decomposes the claim before training
  is spent ([ADR-0094](decisions/ADR-0094-m10-reset.md)).
- **Measure a learning target's label reliability (split-half / test-retest) before building a
  head on it, and read the head's learning curve before scaling data or compute** — an hour of
  diagnostics answered what two build sessions could not
  ([ADR-0096](decisions/ADR-0096-m10-closeout.md)).

- **An exposure split keyed on one arm's own game is post-treatment when exposure correlates
  with survival** (a multi-trigger window, a multi-block: they fire in the games where that seat's
  board lived, i.e. that arm's better games — the split's sign follows the conditioning arm:
  trigger ordering +9.6 ± 2.5 keyed on the served arm, −2.2 ± 2.7 keyed on the withheld arm, the
  same 580 pairs). Attribution is ablation arms on one reference (the ladder); a split is
  exploratory and, if read at all, keyed symmetrically (the window fired in both arms' games).
  ADR-0105 (evening 3).

- **A network arm serves the same tag set as its reference, or the difference is declared as its
  own arm** — every M12 arm from Build 1 served the pay tag at its design init (≈ 0.25 random goal
  payments per game, inside every search copy too) while the `iter-019` reference never carried the
  head: the day-zero cost dz − ref (−1.63 ± 1.15) carries an unmeasured payment-noise term; the
  evening-4 off arm withholds the tag, the ablation arm (e3 pay-withheld vs the evening-3 on arm)
  bounds the term ([ADR-0105 addendum 09-08](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md),
  [ADR-0104 addendum](decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)).
- **A head is served only with a FIT record in the checkpoint** — an "argmax is safe by design"
  init is not a fit: the +2.0-init pay head's pointer residuals deviated on 2.7% of windows for a
  measured −2.56 ± 1.88pp; the server's `has_pay` reads `pay_fit` as `has_surf` reads the surface
  params (the never-serve-fresh-init rule, no exceptions; [ADR-0104 addendum 09-09](decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)).
- **The pool's leaf arithmetic predicts a distilled head's paired read — run the pick-vs-leaf read
  before any arm**: value the head's deviations by the pool's own leaf (pick − auto), positives
  and ties apart, out of sample; the net per deviation forecasts the served read within one SE
  (five pay heads: −1.02 / −1.36 / −1.74 / −0.87 / −0.84 vs a leaf net of ≈ 0). A head whose
  deviations net ≤ 0 by its own label does not serve; a gate must clear the arithmetic's
  precision bar (positives' gain × q − ties' cost × (1 − q) > 0) on the held-out curve before it
  earns a read (`pay_fit --eval`; [ADR-0105 addenda 09-11](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
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
- **A dense aux term never trains on the policy's own emissions
  without a grounded anchor of comparable mass** — self-referential
  decode-on-own-emissions has a degenerate fixed point (empty) and
  reached it in ONE iteration; share guards read the step MEDIAN, and
  a heavy-tailed aux CE gets its own spike tripline
  ([ADR-0085](decisions/ADR-0085-m10-probe1-read.md)).
- **Auto-calibration is unsound for a FIXED SMALL BATCH applied every
  step**: calibrate-then-freeze measures the term pre-application, so a
  memorizable batch delivers full frac-scale mass for a few steps, then
  collapses — the share telemetry only starts after, and the share
  guard is structurally blind to the impulse (170 windows fitted in ~10
  steps doubled the iteration KL)
  ([ADR-0087](decisions/ADR-0087-m10-probe2-read.md)).
- **A small fixed label batch is not a substitute for a dense
  conditioning driver**: certified seed labels at 2× weight moved
  PRESENCE while the content channel went quiet and decode CE on live
  emission rows degraded past day zero — grounded supervision must
  reach trajectory scale to carry the channel
  ([ADR-0087](decisions/ADR-0087-m10-probe2-read.md)).
- **Fixed label batches apply subsampled (one k-chunk per step, epoch-
  shuffled) with a warmup ramp and carry-w**; per-iteration
  recalibration against a partially-fitted batch is an amplifier
  (probe1 grew w_seedlab 12× over three iterations), and the
  memorization tripline (iteration-MIN per-step raw < 0.25×
  raw-at-calibration — per-step keys; the row values are ÷
  traj_per_step, the probe3 false-halt lesson) guards from first
  launch ([ADR-0088](decisions/ADR-0088-grounded-driver.md),
  re-based at [ADR-0090](decisions/ADR-0090-m10-probe4-read.md)).
- **The degeneracy veto's emission axes (pure-hold, length) read
  FIRST-WINDOW emissions only** — revision emissions (opponent-action /
  end-step re-emits, ~80% of emission rows) are legitimately emptier
  late in the turn; the lumped `sched_len_*` counters mis-read probe5
  as drifting to ~28% hold when its first-window hold stayed ≤ 9%
  (ADR-0091 correction; split by the mu `rev` flag until the counters
  split). Full-support emitter labels (certified arm + the natural
  line's witnessed casts) stand as a DESIGN decision — schedule every
  turn — not as a fix for a measured drift
  ([ADR-0092](decisions/ADR-0092-consumer-coupling.md)).
- **Serve-side follow and utilization counters inflate on natural-line
  plans and cannot read consumption** — on windows where the fed plan
  is what the policy would do anyway, fed = closed; a consumption read
  must be schedule-conditioned (fed vs mask-closed, and a legal-
  candidate content swap) on label-shaped inputs
  (`scripts/sched_content_probe.py`; probe6 adjudication,
  [ADR-0093](decisions/ADR-0093-m10-probe6-read.md) addendum).
- **An autoregressive emission head with a STOP class decodes
  stop-vs-continue (p_stop vs Σ candidates), never whole-row argmax**
  — a calibrated head makes STOP the plurality class at every slot ≥ 1,
  and argmax collapses emitted length to ~1 (probe4: 52% pure-hold /
  mean 1.0 against labels at 8% / 2.45); invisible at init, unmasked by
  the first real supervision
  ([ADR-0090](decisions/ADR-0090-m10-probe4-read.md)).
- The standing veto account: under auto-payment, **probing-via-veto IS
  optimal play** — the veto channel is the model's only affordability
  oracle; deterrence-family levers are CLOSED
  ([ADR-0062](decisions/ADR-0062-m8-closeout.md), falsification
  completed at [ADR-0072](decisions/ADR-0072-d4-control-run-veto-collapse-falsified.md)).

- **Under binding execution the natural line is not an independent
  witness**: a window is labeled only if the certifier rolled it out,
  and the label is the search-adjudicated best of {the policy's own
  plan, the enumerated arms} — never label an unrolled window with the
  policy's own play (the ADR-0085 self-target in a new coat)
  ([ADR-0094](decisions/ADR-0094-m10-reset.md)).
- **A distilled clone of the executor cannot learn where the executor is wrong from the
  executor's own features**; search-adjudicated labels need a representation trained on them
  ([ADR-0096](decisions/ADR-0096-m10-closeout.md), the ADR-0050 density argument sharpened).

- **A read on a training population is cross-fit** — when the read's windows are the training
  windows, fold the population by game hash and pool the held-out folds at the cell's full n; a
  single holdout at a fraction of that n cannot resolve the pre-registered bar
  ([ADR-0103](decisions/ADR-0103-m12-build1-value-head-and-build3-enumerators.md)).
- **A gate's bars and its instrument share one scale** — name the read instrument beside the
  bar when the bar is set, and check the instrument can run every arm before pinning it (the
  M12 day-zero read was pinned at K=8/N=600 on the fork-window paired read while its reference
  number lived on the 2,000-game read, and that instrument could not search inside its own
  completions) ([ADR-0104](decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)).

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

- **Critic lookahead is NOT a one-turn labeler; K is the cheap-label dial** — the full-vis
  critic after one applied option ranks the rollout spread at 0.30 (label reliability 0.66) while
  ONE two-turn rollout's composite ranks it at 0.47 at ~2× the copy cost; the learned pivotality
  read-out aims certification at zero search cost (AUC 0.69 vs the critic's 0.65)
  ([ADR-0098](decisions/ADR-0098-build0-critic-lookahead-read.md)).

## Engine, fork, and data hygiene

- **Replaying a model-generated store requires the generating run's
  trajectory-perturbing flag set (-reask/-paytelemetry/... from ITS
  run.json) AND its serve config (ckpt, sampled, temperature), and
  parity is WITNESSED by an obs decision-stream comparison, never
  argued** (`sched_mint.py parity`;
  [ADR-0088](decisions/ADR-0088-grounded-driver.md)).
- **Stores with overlapping game-index ranges never replay concurrently
  against one carry-stateful server** — the serve carry is keyed
  (g, seat), so cross-store collisions flip answers at emission windows
  (97% of games diverged in the first mint run; phased-by-store is the
  safe shape until carry is channel-keyed — routed serve-hardening
  item; ADR-0088 addendum).
- **Every input to the serve path must be replay-stable, and the obs
  seq is a serve input** (sampling noise is keyed (game_seed, s)) — any
  machinery that adds or removes obs records relative to generation
  shifts the POLICY, not just bookkeeping (Obs.mark consumed one id per
  fork point and re-rolled every post-fork decision; fixed at fork
  `f9eadfa8d4`; [ADR-0089](decisions/ADR-0089-mint-replay-integrity.md)).
- **Bridged JVMs leak one game graph per game unless AiCache is cleared
  between games — chunk recycling is load-bearing**; never run a
  bridged JVM unbounded without one or the other (upstream
  `AiCache.dataMap` clears only on the heuristic AI priority path
  bridged seats never take; heap-dump-proven at the M10 sweep OOM;
  within-game clears = a boundary-event candidate
  ([ADR-0078](decisions/ADR-0078-m10-ceiling-measurement.md))).
- **Every Anvil-side scan or test that touches engine code runs on a throwaway RNG**
  (`AnvilOptions.withScratchRng`): Forge's legality/payability helpers draw from the game
  RNG (`isManaSourceReserved` → `MyRandom.percentTrue` on every shard × source), so an
  unguarded scan perturbs the trajectory a seed plays and any skipped scan (a cache hit)
  shifts the stream — the D2 "`-obs` perturbs" finding, explained and closed at Build 0
  ([ADR-0102 addendum](decisions/ADR-0102-m12-build0-pins.md)). The obs-diff gate
  (`scripts/obs_diff.py`, first-divergence classes) is the witness.
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
- **Replay parity of a SAMPLED mainline is bounded by serving jitter (~20% of games flip a
  near-tied pick under micro-batch composition)**: replay instruments pair within-run (CRN) and
  budget cross-run divergence, never assume it ([ADR-0096](decisions/ADR-0096-m10-closeout.md)).

- **Readers over fork/trajectory stores STREAM one game (or one window's completions) at a time
  and keep floats only; big reads/ingests launch under a cgroup cap** (`systemd-run --user --scope
  -p MemoryMax=…`) — decoded obs are ~10× raw JSON in Python objects; a retained-trajectory read
  of 96K completions hit 51.6 GB and OOM-killed the desktop session 2026-09-06
  ([ADR-0098](decisions/ADR-0098-build0-critic-lookahead-read.md)).

## Scoping and routing

- **Measuring a ceiling is not evidence a route can learn it**: a label route funds its mint only
  after a learnability read at ~10³ windows clears a pre-registered bar ABOVE a trivial prior on
  the same holdout (arm length 0.15, the auto-correct sign prior 0.42 — ADR-0099)
  ([ADR-0100](decisions/ADR-0100-m11-closeout.md)).
- **Plan-type (composite) option quality is not regressible from the pre-action state at harvest
  scale** — three head shapes, two targets, both trunk modes; a future plan-type surface shows a
  within-window ranking above a length prior before a training run funds it
  ([ADR-0099](decisions/ADR-0099-build1-scorer-kill.md), [ADR-0100](decisions/ADR-0100-m11-closeout.md)).
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
- **Every store row carries an explicit format id and pool id**, and a new format onboards by
  the recipe doc (`docs/design/format-onboarding.md`) as one boundary event — extends the
  content-in-chunks rule to formats
  ([ADR-0101 addendum](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **A binding execution regime is gated by a DAY-ZERO read of the
  planner against the executor it replaces** — binding pays only where
  the planner is at least the executor's equal at the bound windows
  (the distilled planner read −6.7pp as pinned and −4.5pp binding its
  first slot alone; the damage is monotone in the amount bound)
  ([ADR-0095](decisions/ADR-0095-m10-dayzero-read.md)).
- **One decision MECHANISM per milestone; surfaces attribute through
  per-tag reads** (the certifier's per-tag spreads + the paired read with
  the mask closed per tag) — amends design-doc §3d′'s "one decision
  surface per milestone", which still binds any surface lacking its own
  per-tag read ([ADR-0097](decisions/ADR-0097-m11-charter-adjudication.md)).
- **Design forks lead with the simpler, more coherent architecture and
  price its extra data/compute honestly** (user principle, stated at the
  M10 reset), **and a build is staged around its cheapest decisive read**
  (the day-zero read needed a third of the build)
  ([ADR-0094](decisions/ADR-0094-m10-reset.md)).

## Search, budgets, and run sizing

- **Size every run to its effect**: a power statement (games needed to detect the target,
  games needed to produce it) precedes every launch; a gate that cannot resolve the effect it
  seeks is a null generator, not a measurement
  ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **The natural line is always in the searched option set**; under a margin-gated acting rule a
  surface cannot be dramatically worse than its fallback, so search-acted surfaces bundle
  without per-surface attribution (amends the ADR-0097 one-mechanism rule for search-acted
  surfaces only) ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **Search budgets are in evaluations during training, never wall-clock**; a per-device
  calibration map converts at deployment; the model never sees the clock
  ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **A gated search keeps a uniform exploration floor**, and its pivotality labels are the
  search's own margins, era-scoped and regenerated per cycle (the §3d self-sealing hazard)
  ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **Every search cost is priced per game against generation rate**; throughput is the binding
  constraint until measured otherwise
  ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **The mask's legality predicate is the executor's apply-time predicate** — filter and
  adjudicator agree by construction; residual veto classes are counted by name, never absorbed
  by a penalty or a guard ([ADR-0102](decisions/ADR-0102-m12-build0-pins.md)).
- **An ability's identity in the observation is its canonical engine text, keyed by hash** —
  the script parameters + description the fork emits (`ak` on every ability-bearing option and
  answer; `AnvilRun -abilities` for the pool), never a display render; every consumer of ability
  text (priority candidates, surface options, stack entries) reads ONE shared table
  ([ADR-0105](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
- **An ability's key is a function of its STATIC canonical text — runtime state never enters it**
  (a trigger's run-parameter dump, a granted or copied ability's source attribution: 10,325
  one-off keys in 1,000 games before `AbilityKey.stripRuntime`); the proof of any change to the
  key function is the byte-identical pool re-dump (5,148 keys, the same set), so every `ak` in
  every store stays valid ([ADR-0105 addendum 09-08](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
- **A probe on the game path is game-neutral — RNG AND engine memory**: the payment window's
  auto-payability test (`ComputerUtilMana.canPayManaCost` in test mode) drew the game RNG per
  candidate source and cleared / wrote the AI's mana-reservation sets on every bridged window
  before the real payment; a bridged seat answering auto everywhere lost ≈ 2.7pp (three reads);
  every enumeration / legality / payability probe runs under `AnvilOptions.withScratchRng` and
  restores what it can touch (`PlayerControllerAnvil.quietProbe`), and a served-vs-withheld read
  proves it before a head is read through it ([ADR-0105 addendum 09-09](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
- **A search copy is determinized to the acting seat's information set**: hidden zones are
  resampled, never carried true, and the sampler is a named teacher setting in the store's
  provenance; a value computed on a true-hand copy leaks regardless of channel width
  ([ADR-0102](decisions/ADR-0102-m12-build0-pins.md)).
- **A big run is preceded by a shakedown run of the same loop shape** (~10% of its size, every
  flag on) that tests the training settings under the new label mix and supplies the
  learning-curve slope for the power statement's "games to produce" line
  ([ADR-0101 addendum](decisions/ADR-0101-architecture-review-m12-recharter.md)).
