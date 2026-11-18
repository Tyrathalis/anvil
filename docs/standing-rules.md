# Standing rules

One line per rule, grouped by when you need it, each linked to the ADR
that gave rise to it. This is the consolidated register — milestone bullets in
CLAUDE.md no longer enumerate rules, they point here. **Read the
relevant section before designing any run, gate, instrument, or
curation cycle.** (The seven design invariants stay in CLAUDE.md; this
file is the operational layer under them.)

Maintenance: when an ADR births a rule, add it here in the same commit
batch; when a rule is superseded, or its mechanism leaves the recipe, move
it verbatim to [standing-rules-retired.md](standing-rules-retired.md) with
the date and the reason — never silently delete. A rule is capped at about
two lines: the rule and at most one clause of why. The numbers, the runs and
the story stay in its ADR.

## Gates, reads, and statistics

- Gate a capability on a **discrimination statistic**, never an accuracy count. A sub-population with zero correct at day zero is a gate defect ([ADR-0069](decisions/ADR-0069-d4-read-adjudication.md)).
- **Measure the ceiling before building the learner** ([ADR-0073](decisions/ADR-0073-m9-ceiling-measurement.md)).
- **Per-window value and gate-scale value are distinct claims.** A ceiling statement carries both ([ADR-0073](decisions/ADR-0073-m9-ceiling-measurement.md)).
- A re-certification threshold on a selected population prices **winner's-curse regression**, not only drift ([ADR-0073](decisions/ADR-0073-m9-ceiling-measurement.md)).
- **Read every pre-registered signal** before closing a run's verdict ([ADR-0069](decisions/ADR-0069-d4-read-adjudication.md)).
- A recipe pin that removes a condition is **re-checked against every pre-registered readout**. A control restores the condition, not the asset ([ADR-0069](decisions/ADR-0069-d4-read-adjudication.md), [ADR-0072](decisions/ADR-0072-d4-control-run-veto-collapse-falsified.md)).
- An evalset's **certification horizon is part of its type**. "Certified" never stands unqualified in a strength argument ([ADR-0072](decisions/ADR-0072-d4-control-run-veto-collapse-falsified.md)).
- **A fixed-subset arms read is one observation, not N.** A small-N arms tease near 1.5σ is a recurring artifact, three instances on file ([ADR-0058](decisions/ADR-0058-m7-closeout.md)).
- **A single-seed-set read at about 1pp is inconclusive.** The combined paired read is the standard ([ADR-0037](decisions/ADR-0037-m5-closeout.md)), and a fresh-seed paired confirmation breaks a marginal t ([ADR-0033](decisions/ADR-0033-m4-closeout.md)).
- When a gate goes flat while instruments improve, **audit the signal path before reaching for the next lever** ([ADR-0049](decisions/ADR-0049-flat-cycle-audit.md)).
- Battery findings are **exploratory only**. Verdicts stay pre-registered ([run-analysis-protocol](design/run-analysis-protocol.md)).
- **A probe's primary read is a strength read on the funded stratum with the ceiling's own paired instrument.** Competency proxies are exploratory, and a day-zero read decomposes the claim before training is spent ([ADR-0094](decisions/ADR-0094-m10-reset.md)).
- **Measure a learning target's label reliability before building a head on it** (split-half or test-retest), and read the head's learning curve before scaling data or compute ([ADR-0096](decisions/ADR-0096-m10-closeout.md)).
- **An exposure split keyed on one arm's own game is post-treatment when exposure correlates with survival.** Attribution is ablation arms on one reference; a split is exploratory and keyed symmetrically if read at all ([ADR-0105](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
- **A network arm serves the same tag set as its reference**, or the difference is declared as its own arm ([ADR-0105](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md), [ADR-0104](decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md) addenda).
- **A head is served only with a fit record in the checkpoint.** An init that is "safe by design" is not a fit, and there are no exceptions ([ADR-0104](decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md) addendum).
- **Run the pick-vs-leaf read before any arm of a distilled head.** Value the head's deviations by the pool's own leaf, out of sample, positives and ties apart. A head whose deviations net ≤ 0 does not serve, and a gate clears the arithmetic's precision bar on the held-out curve before it earns a read ([ADR-0105](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md) addenda).
- **A pre-registered tie-break that names "the cheaper arm" defines cheaper at registration**, as forward calls per game ([ADR-0115](decisions/ADR-0115-m12-shakedown-scoping.md)).
- **A control for a label-side check contains the labelling seat.** A model self-play store cannot miss its own options, so read the store manifest's bridge and seats before citing a control ([ADR-0122](decisions/ADR-0122-union-target-mask.md) addendum).

## Training-loop design

- **Clips at birth** for engineered aggregates and for loss terms ([ADR-0050](decisions/ADR-0050-m6-closeout.md), [ADR-0056](decisions/ADR-0056-run14-seq-divergence.md)).
- Auto-calibrated weights get their invariant **instrumented, guarded, and recalibrated at the cadence it varies**. Per-iteration recalibration is the default ([ADR-0057](decisions/ADR-0057-run15-share-drift.md)).
- **An aux target's shape is a behavioral prior.** What the latent predicts is what the policy is nudged to enact ([ADR-0076](decisions/ADR-0076-d6-probe-read.md)).
- Price a conditioning channel's lr by its **gradient density, not its init** ([ADR-0076](decisions/ADR-0076-d6-probe-read.md)). The starved-parameter arithmetic applies to heads fed by rare windows ([ADR-0069](decisions/ADR-0069-d4-read-adjudication.md)).
- **Falling reliance with compounding behavior is absorption**, not disuse. Read the flip metric jointly with the behavioral series ([ADR-0076](decisions/ADR-0076-d6-probe-read.md)).
- A guard-halt relaunch after a **recipe change clears the rejected phase's artifacts** (archive, do not delete). Phase reuse is for crashes, not amendments ([ADR-0076](decisions/ADR-0076-d6-probe-read.md)).
- **Probe first**: a short run with a pre-registered kill signal precedes any promotion-scale run ([ADR-0076](decisions/ADR-0076-d6-probe-read.md)).
- **A dense aux term never trains on the policy's own emissions without a grounded anchor of comparable mass.** Share guards read the step median, and a heavy-tailed aux CE gets its own spike tripline ([ADR-0085](decisions/ADR-0085-m10-probe1-read.md)).
- **Auto-calibration is unsound for a fixed small batch applied every step.** The batch is memorized within steps of calibration, and the share guard is blind to the impulse ([ADR-0087](decisions/ADR-0087-m10-probe2-read.md)).
- **A small fixed label batch is not a substitute for a dense conditioning driver.** Grounded supervision reaches trajectory scale before it can carry a channel ([ADR-0087](decisions/ADR-0087-m10-probe2-read.md)).
- **Fixed label batches apply subsampled** (one k-chunk per step, epoch-shuffled) with a warmup ramp and a carried weight. A memorization tripline on per-step keys guards from first launch: the iteration minimum under 0.25× the raw value at calibration ([ADR-0088](decisions/ADR-0088-grounded-driver.md), [ADR-0090](decisions/ADR-0090-m10-probe4-read.md)).
- The standing veto account: under auto-payment, **probing by veto is optimal play**, because the veto channel is the model's only affordability oracle. Deterrence-family levers are closed ([ADR-0062](decisions/ADR-0062-m8-closeout.md), [ADR-0072](decisions/ADR-0072-d4-control-run-veto-collapse-falsified.md)).
- **A distilled clone of the executor cannot learn where the executor is wrong from the executor's own features.** Search-adjudicated labels need a representation trained on them ([ADR-0096](decisions/ADR-0096-m10-closeout.md)).
- **A read on a training population is cross-fit**: fold by game hash and pool the held-out folds at the cell's full n ([ADR-0103](decisions/ADR-0103-m12-build1-value-head-and-build3-enumerators.md)).
- **A gate's bars and its instrument share one scale.** Name the read instrument beside the bar when the bar is set, and check that it can run every arm before pinning it ([ADR-0104](decisions/ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)).
- **A value head that trains inside the loop is audited against rollout truth every iteration** (`value_pretrain eval` on the frozen holdout). A head that also serves as the search's leaf is anchored to that truth, because outcome targets alone pull it off ([ADR-0118](decisions/ADR-0118-value-head-drift-under-the-loop.md)).
- **An anchor bank is read on its training rows beside its holdout**; a growing gap is the anchor memorizing. Size the bank and the draw budget so one iteration stays under a pass, and never raise the anchor weight to fix a sliding holdout ([ADR-0124](decisions/ADR-0124-anchor-bank-refresh.md)).
- **Adding or removing a loss on a shared trunk re-sizes every other loss's step under AdamW.** Before such a cell, replay one iteration on an existing store, re-match `kl_mu` to the control, and pin `--trunk-lr` and `--value-head-lr` in the recipe ([ADR-0119](decisions/ADR-0119-value-function-first-before-the-big-run.md) addendum).

## Curation, drills, and the critic

- **Drill mainlines never enter training ingest.** Curation regenerates from the current checkpoint of record's own losses every cycle, and selection and evalset versions are scoped to the checkpoint era ([ADR-0033](decisions/ADR-0033-m4-closeout.md), [ADR-0031](decisions/ADR-0031-a2-resolution.md)).
- **The migration read gatekeeps cycle pricing** (`scripts/migration_read.py`, [ADR-0037](decisions/ADR-0037-m5-closeout.md)).
- **Critic ordering is not evidence in loss-adjacent populations.** Ranking comes from rollouts ([ADR-0036](decisions/ADR-0036-d3-critic-calibration.md)); critic-classified fractions are instrument-limited ([ADR-0037](decisions/ADR-0037-m5-closeout.md)).
- **Isotonic maps are era-scoped assets.** The value-audit label set grows with every map and sweep ([ADR-0036](decisions/ADR-0036-d3-critic-calibration.md)).
- **Probe on `[STATE]`, never the trained head.** Inner-validation pools are pinned ([ADR-0050](decisions/ADR-0050-m6-closeout.md)).
- Mid-campaign checkpoints **sweep the two leading Ns** ([ADR-0050](decisions/ADR-0050-m6-closeout.md)).
- Check whether candidate curation stock is **gate-seeded** before using it: `m9-rebaselinearm` shares `final_read.py`'s seed base ([ADR-0068](decisions/ADR-0068-m9-boundary-bundle.md)).
- **Curriculum composition (the behind/ahead balance) is a first-class lever** ([ADR-0033](decisions/ADR-0033-m4-closeout.md)).
- **Veto-elevated run stores never enter a training mixture**, permanently: run14/15/16 ([ADR-0058](decisions/ADR-0058-m7-closeout.md)) and run18/19/20 ([ADR-0077](decisions/ADR-0077-m9-closeout.md)).
- **Critic lookahead is not a one-turn labeler; K is the cheap-label dial.** One two-turn rollout out-ranks the critic after one applied option, and the learned pivotality read-out aims certification at no search cost ([ADR-0098](decisions/ADR-0098-build0-critic-lookahead-read.md)).
- **A replay coordinate names the seat's natural pick, its turn, its phase and the seat profiles.** The fork point is that pick's window, continued through the seat's own chooser under the pre-decision RNG, never the first window holding the option and never a re-approval through `canPlaySa`. An opponent-turn or in-response cast reads `never_fired` ([ADR-0117](decisions/ADR-0117-certifier-merge.md)).

## Engine, fork, and data hygiene

- **A convention is checked through the model's row space, not by label↔decode agreement.** Every head with a player or seat reference gets a permutation test over the whole path: swap the registered seats, and the decoded engine object must be the same object ([ADR-0116](decisions/ADR-0116-player-target-positions.md)).
- **Every read reports the target-sanity row**, the model's self-target rate beside the heuristic's in the same games. A checkpoint records its label conventions and a loader refuses a mismatch ([ADR-0116](decisions/ADR-0116-player-target-positions.md)).
- **A format addition edits the vocab row and the feature column and nothing else.** Every asset and checkpoint reads through `transform.globals_layout`, the change lands with the identity test green, and the first data in the format is the boundary event ([ADR-0120](decisions/ADR-0120-constructed-model-row.md)).
- **A chance event that voids knowledge the ledger tracks is a stream record, not an inference.** The shuffle is a store-frame mark from the engine's own event, and the ledger cleanses its poison, tuck and seen state on it ([ADR-0121](decisions/ADR-0121-shuffle-mark.md)).
- **A legality mask on a learned pointer is proven on a corpus before it serves**: every expert-chosen label inside the mask, the bar zero. An option the engine cannot enumerate faithfully is declared unmasked, never given a wrong set ([ADR-0122](decisions/ADR-0122-union-target-mask.md)).
- **Replaying a model-generated store requires the generating run's trajectory-perturbing flags and its serve config** (checkpoint, sampled, temperature), both from its `run.json`. Parity is witnessed by an obs decision-stream comparison, never argued (`sched_mint.py parity`; [ADR-0088](decisions/ADR-0088-grounded-driver.md)).
- **Stores with overlapping game-index ranges never replay concurrently against one carry-stateful server.** The serve carry is keyed (game, seat), so phase by store until the carry is channel-keyed ([ADR-0088](decisions/ADR-0088-grounded-driver.md) addendum).
- **Every input to the serve path is replay-stable, and the obs seq is a serve input.** Machinery that adds or removes obs records relative to generation shifts the policy, not just bookkeeping ([ADR-0089](decisions/ADR-0089-mint-replay-integrity.md)).
- **A bridged JVM leaks one game graph per game unless `AiCache` is cleared between games, so chunk recycling is load-bearing.** Never run a bridged JVM unbounded without one or the other ([ADR-0078](decisions/ADR-0078-m10-ceiling-measurement.md)).
- **Every Anvil-side scan or test that touches engine code runs on a throwaway RNG** (`AnvilOptions.withScratchRng`), because Forge's legality and payability helpers draw from the game RNG. `scripts/obs_diff.py` is the witness ([ADR-0102](decisions/ADR-0102-m12-build0-pins.md) addendum).
- **Engine upgrades are dataset-boundary events.** The behavior-identical exemption is proven empirically (same seeds, identical forkcheck trace hashes), never argued; `forkcheck` at the BC certification checkpoint is the bump gate ([ADR-0025](decisions/ADR-0025-d4-rebase-closeout.md)).
- **An engine bump lands as a merge with a pre-merge tag, never a rebase.** The fork's tip hashes are cited by run headers, ADRs and forkcheck records and must stay resolvable ([ADR-0110](decisions/ADR-0110-m12-upstream-merge-20260916.md)).
- **Every pre-boundary number is old-scale.** Never compare winrates across eras, and compare generation times across eras only at identical chunking ([ADR-0025](decisions/ADR-0025-d4-rebase-closeout.md), [ADR-0033](decisions/ADR-0033-m4-closeout.md)).
- An enumerator's **unit of exclusivity is the unit the executor consumes** ([ADR-0066](decisions/ADR-0066-certify-salvage-host-exclusivity.md)). A certified "best" over rolled-out arms is a class statement, and a consumer collapsing it to one index shows the collapse is behavior-neutral ([ADR-0082](decisions/ADR-0082-payment-evalset-repair.md)).
- **`sa_vocab` is pinned and never regenerated in place** ([ADR-0012](decisions/ADR-0012-d2-d3-closeout.md)). Obs schema eras never mix; the reader gate is strict ([ADR-0068](decisions/ADR-0068-m9-boundary-bundle.md)).
- **Never read a bridge answer field without checking `fallback` first.** Eval runs keep census and obs on, and zero-error validation is the corpus-launch gate ([ADR-0009](decisions/ADR-0009-m1-closeout.md)).
- **BC is finished as a strength program** ([ADR-0012](decisions/ADR-0012-d2-d3-closeout.md)).
- Milestone close includes the **stale-data deletion pass**; its steps and its unconditional keeps are in CLAUDE.md's session wrap-up checklist.
- Standing hazards: the playable build shares Forge's user deck store with research (`launch --pool` hash-gates it). **Never check out `playable` in the research worktree.** Pool selection rides `data/pool/CURRENT`, never mtime.
- **Replay parity of a sampled mainline is bounded by serving jitter.** Replay instruments pair within-run and budget cross-run divergence, never assume it ([ADR-0096](decisions/ADR-0096-m10-closeout.md)).
- **Readers over fork and trajectory stores stream one game, or one window's completions, at a time and keep floats only.** Big reads and ingests launch under a cgroup cap (`systemd-run --user --scope -p MemoryMax=…`) ([ADR-0098](decisions/ADR-0098-build0-critic-lookahead-read.md)).
- **Every detached run launches through `uv run python -m anvil.runs launch --name <run> --dir <dir> --launched-by '<name> [<ref>]' -- <cmd>`.** Its coverage line is the only coverage a session claims, and chains whose arms write elsewhere add `--watch`. The launching session owns the close and arms its own background wait. A relayed event for a run you did not launch is informational: read the state file's `launched_by` and `git log -3` before writing, one record per event ([ADR-0107](decisions/ADR-0107-run-launcher-and-checkin.md) and addenda).
- **A horizon calibration's outcome arm runs under an independent roll salt** (`-searchrollsalt`), because under common random numbers the deeper leaf's agreement with the outcome is optimistic by construction. The rate draw stays unsalted so the arms join per window ([ADR-0106](decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md) addendum).
- **A surface's hook site is verified by the census counts before the hook lands.** The AI decides inside its own logic, not at the controller callback, and a hook on the wrong site records nothing while looking complete ([ADR-0111](decisions/ADR-0111-m12-build4-opening-targets-surface-site.md)).
- **An ability table crosses an engine boundary by extension, never a rebuild**: base rows byte-identical, new keys embedded under a revision check, dropped keys kept. An older build serves the superset through `bridge.server --abilities`, so a reference arm carries no OOV confound ([ADR-0111](decisions/ADR-0111-m12-build4-opening-targets-surface-site.md)).
- **A distillation that shapes a subset of windows anchors the rest to the teacher**, or the shared heads generalize freely on the unshaped windows ([ADR-0111](decisions/ADR-0111-m12-build4-opening-targets-surface-site.md)).
- **A trainer's join reports its match rate before its first fit** ([ADR-0111](decisions/ADR-0111-m12-build4-opening-targets-surface-site.md)).
- **The search values only what the decoder can plan, so the void class is a coverage bound, not a copy-fidelity artifact.** Read the void class by reason (`vr`) before sizing an arm. The route to it is the loop's policy gradient on the decoder's own casts, with no offline rescue ([ADR-0114](decisions/ADR-0114-m12-route-b-rescoped-void-rescue.md)).

## Scoping and routing

- **Measuring a ceiling is not evidence a route can learn it.** A label route funds its mint only after a learnability read at about 10³ windows clears a pre-registered bar above a trivial prior on the same holdout ([ADR-0100](decisions/ADR-0100-m11-closeout.md)).
- **Plan-type (composite) option quality is not regressible from the pre-action state at harvest scale.** A future plan-type surface shows a within-window ranking above a length prior before a training run funds it ([ADR-0099](decisions/ADR-0099-build1-scorer-kill.md), [ADR-0100](decisions/ADR-0100-m11-closeout.md)).
- **Every deferral is routed by name** at the next scoping session and the closeout ADR: scheduled, or re-deferred with a recorded reason, never silently lost ([ADR-0077](decisions/ADR-0077-m9-closeout.md)).
- **Capabilities over heuristic fallback** (user default): keep or add model capabilities unless dramatically weaker, on the compounding-surface hypothesis.
- **Promote on cleared gate** (user default) unless the run itself is suspect.
- Content breadth scales in set-sized dataset-boundary chunks after core features, recipe first ([ADR-0018](decisions/ADR-0018-ruleset-scope-clarification.md)).
- **Every store row carries an explicit format id and pool id.** A new format onboards by [format-onboarding.md](design/format-onboarding.md) as one boundary event; the [quickstart](design/quickstart-custom-pool.md) is its Constructed instance ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md) addendum).
- **One decision mechanism per milestone; surfaces attribute through per-tag reads.** The design doc's "one decision surface per milestone" still binds any surface without its own per-tag read ([ADR-0097](decisions/ADR-0097-m11-charter-adjudication.md)).
- **Design forks lead with the simpler, more coherent architecture and price its extra data and compute honestly** (user principle). A build is staged around its cheapest decisive read ([ADR-0094](decisions/ADR-0094-m10-reset.md)).

## Search, budgets, and run sizing

- **An arm's box time is the driver's accumulated wall (`selfplay.py --wall-hours`), never its game count.** A paused arm resumes its budget ([ADR-0115](decisions/ADR-0115-m12-shakedown-scoping.md)).
- **A calibrated timing launches with `--quiet-box`.** It starts only on an idle box, and other launches and the pre-push hook wait for it ([ADR-0107](decisions/ADR-0107-run-launcher-and-checkin.md), 11-18 addendum).
- **A deliberate stop is `anvil.runs pause`, a return `relaunch`, and a long run launches with `--resume-on-gone`.** A job idle on purpose heartbeats the run dir, so the stall alarm and the failed push stay for what went wrong ([ADR-0107](decisions/ADR-0107-run-launcher-and-checkin.md) addendum).
- **A long run is segmented by its wall budget, never by chained loops**: one loop, one state file, one replay window, one drift series. The loop's wall stop is the review point, and the next segment is the same command relaunched with the budget raised ([ADR-0123](decisions/ADR-0123-big-run-launch.md)).
- **Size every run to its effect.** A power statement (games to detect the target, games to produce it) precedes every launch; a gate that cannot resolve its effect is a null generator ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **The natural line is always in the searched option set.** Under a margin-gated acting rule a surface cannot be dramatically worse than its fallback, so search-acted surfaces bundle without per-surface attribution; this amends the one-mechanism rule for them only ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **Search budgets are in evaluations during training, never wall-clock.** A per-device calibration map converts at deployment, and the model never sees the clock ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **A gated search keeps a uniform exploration floor.** Its pivotality labels are the search's own margins, era-scoped and regenerated per cycle ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **An identity gate on a served arm runs one worker.** Under bf16 autocast the micro-batch composition flips near-tie argmax picks, so a multi-worker obs-diff cannot separate a code change from serve nondeterminism ([running record](design/m12-running-record.md), 2026-09-14).
- **A search run's load is part of its recipe.** Workers × servers are pinned per run, under the core ceiling (24 workers on the 32-core box) and one server per 12 workers. Served runs are not seed-reproducible across fleet configurations, so a paired read pins its fleet on both arms ([running record](design/m12-running-record.md), 2026-09-14).
- **Search recipes are compared at equal box time, never equal games, and the read is the network-alone gain per box-hour.** A two-budget read on a fixed checkpoint answers the serving-budget question instead. "No detectable difference" is itself the decision: the cheaper arm ([ADR-0106](decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md)).
- **Every search cost is priced per game against generation rate.** Throughput is the binding constraint until measured otherwise ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
- **A served surface answer is realized with everything the heuristic's answer bundles.** Read the engine's realization path for what the heuristic decides jointly before serving the callback alone; where the bundle cannot be served, the search copy plays the pair and the leaf judges it ([ADR-0108](decisions/ADR-0108-m12-build3-closeout.md)).
- **Surface coverage closes before a big run, not after.** A decision family the heuristic still owns at launch gets no policy gradient and no lookahead for the whole run; the pre-launch audit sets the engine's decision API against the bridged tags and hooks ([ADR-0109](decisions/ADR-0109-prelaunch-completeness-audit.md)).
- **A search shape's per-copy price is measured on the calibration arms before its arm is sized.** Assumed multipliers do not size arms ([ADR-0106](decisions/ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md) C3 addendum).
- **The mask's legality predicate is the executor's apply-time predicate.** Residual veto classes are counted by name, never absorbed by a penalty or a guard ([ADR-0102](decisions/ADR-0102-m12-build0-pins.md)).
- **An ability's identity in the observation is its canonical engine text, keyed by hash** (`ak`), never a display render. Every consumer of ability text reads one shared table ([ADR-0105](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md)).
- **An ability's key is a function of its static canonical text; runtime state never enters it.** The proof of any change to the key function is the byte-identical pool re-dump ([ADR-0105](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md) addendum).
- **A probe on the game path is game-neutral in RNG and in engine memory.** Every enumeration, legality or payability probe runs under `withScratchRng` and restores what it can touch (`quietProbe`), and a served-vs-withheld read proves it before a head is read through it ([ADR-0105](decisions/ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md) addendum).
- **A search copy is determinized to the acting seat's information set.** Hidden zones are resampled, never carried true, and the sampler is a named teacher setting in the store's provenance ([ADR-0102](decisions/ADR-0102-m12-build0-pins.md)).
- **A big run is preceded by a shakedown run of the same loop shape**, about 10% of its size with every flag on. It tests the training settings and supplies the slope for the power statement's "games to produce" line ([ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md) addendum).
- **An allocation gate's ask is a server ask on the value wire, declined without a fit record.** No default rate is baked into the engine, and an unfitted head never allocates: the worker searches at its uniform rate ([ADR-0112](decisions/ADR-0112-m12-build4-allocation-head-served.md)).
- **An acted window's training record is the search's, merged from the engine's two records**: the full option set, the acted candidate as the choice, the search's mass on it as the behavior probability. A window whose record cannot be built is dropped, never trained under the policy's own mu ([ADR-0113](decisions/ADR-0113-m12-loop-wiring.md)).
- **Drift guards and the mu tripwire read un-acted windows only** on a searched store. The acted windows' fraction, ratio and KL are their own telemetry series ([ADR-0113](decisions/ADR-0113-m12-loop-wiring.md)).
- **The allocation head's tau is re-derived every cycle on the searched windows weighted to the population**, and written into the checkpoint's fit record. The floor's windows alone are not an unbiased sample ([ADR-0113](decisions/ADR-0113-m12-loop-wiring.md)).
- **The trainer reconstructs every serve-side carry the server activates for the serving checkpoint**; the driver probes the checkpoint (`--sched-carry auto`). The sampled serve path is smoked whenever a serve tag or carry lands ([ADR-0113](decisions/ADR-0113-m12-loop-wiring.md) addendum).
