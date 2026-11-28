# Review of the 2026-11-27 codebase audit

**Doc status:** survey · a second session's review of the 11-27 audit of the Python tree and the research fork (branch `anvil-audit-fixes` in both repositories): which measurements were re-checked, what is wrong in the patches, how the audit's one commit was split, and what remains unverified. Taken 2026-11-27 beside the live `m13-nosearch` arm. A record; not rewritten.

## Verdict

The audit found real defects, and every measurement this review re-checked holds.
Its patches should not merge as written.
One patch would have vetoed most X spells on the pinned jar.
Several changes it calls zero-boundary bugfixes are recipe changes or boundaries.
Its headline, that these defects "explain much of the current training plateau", has no experiment behind it.

The audit's one Python commit and one fork commit are now split into three branches, one change per commit.
Nothing is merged.
`audit-land-now` lands at search off's close, on the user's word.

## What was reviewed

- The audit's two documents: `docs/design/anvil-audit-2026-11-27.md` on Anvil's `anvil-audit-fixes`, and `docs/Development/anvil-audit-2026-11-27.md` on the fork's branch of the same name. Neither is on main.
- The Python commit `986d4c8` (14 files, +1,247 / −77) and the fork commit `a60b3e1ea2` (11 files, +442 / −51), read in full.
- The audit's measured claims, against checkpoints and run data on this box.

The review ran no training and no games.
It ran the Python tests of the split branches and one compile of the fork branch.

## Measurements re-checked

| Audit claim | How it was checked | Result |
|---|---|---|
| The trainer never loads the ability table | Per-family weight diff, `m12-build4-e1a-tgt/last.pt` against `m13-control/iter-064/train/last.pt`; `rl.py` on main has no `set_ability_table` call | Holds. `cand_abil_proj` is exactly zero in both. The first 2,560 columns of `stack_host_proj`, `stack_tgt_proj` and `stack_state_proj` are exactly zero. |
| The served surface heads are frozen on a drifting trunk | Same diff | Holds. `surf_query`, `surf_key` and the three surface embeddings have zero drift. The trunk moved 2.5% (relative L2). |
| The X head is about a third of policy entropy | 200,000 rows of `m13-control/iter-064/mu.jsonl` | Holds: 31.2% of summed recorded entropy. Mean absolute X log-probability per cast is 0.51, against 0.045 for targets. X picks spread over 2, 3, 0, 16, 13, 17. |
| Monte Carlo rollouts reach the live bridge | `mu.jsonl.counts.json` across runs; the fork's `GameCopier.clonePlayer` and `AnvilLobbyPlayer` | Holds. `m13-control/iter-000` counts 22,650 priority, 7,724 attack and 2,347 block fallbacks, as the audit states, and 782 model errors in `server.log`. `m13-nosearch/iter-000` shows the same pattern; `big-run/iter-405` and `iter-300` show none. The source is the Monte Carlo opponent, not search. |
| The allocation threshold is drifting | `train/search_join.json` per iteration | Holds: tau 0.038, 0.025, 0.019, 0.016, 0.0078 at iterations 0, 16, 32, 48, 64. |
| Voided games are scored | grep of every consumer of `games.jsonl` status | Holds, and wider than stated. No consumer outside the orchestrator knew `yield_clock`. Four voided games exist, all in `m13-nosearch` generation. |
| The surface decode applies temperature twice | `cat_pick` against `_surface_decode` in `model.py`; `make_noise`'s docstring | Holds. The noise is already scaled by the temperature. At temperature 1 the two forms are equal. |

Not re-checked, and so neither confirmed nor refuted here:

- That 425 of 425 counterspells on the stack serialize with no target.
- That transformed cards and clones serialize under their printed front-face name.
- That 0.86% of casts carry an X cost. The audit's own count probably used the text match this review found faulty.
- The entropy shares at `big-run/iter-000` (48.5%) and `m13-control/iter-000` (35.8%).
- That the mode gate's unguarded probe shifts results by about 3pp. The figure is borrowed from the payment probe's history.
- The determinization and leaf-horizon observations, and the size estimates for `AnvilRun.java`.
- The audit's "116 passed". This review ran its own subsets.

## What is wrong in the patches

1. **The X mask's fallback broke X spells.**
   The patch masks the X head unless the option is an X cost.
   For a jar without the new flag it matched the option text for `{X}` in the cost prefix or the words "Pay X ".
   Recorded option text shows most X spells name no cost: "Search your library for a creature card with mana value X or less", "As an additional cost to cast this spell, pay X life", "deals X damage to any target".
   `CastPlanRealizer.tryApply` returns false for an X spell whose plan carries no X.
   On the pinned jar those casts would have been vetoed.
   The realizer's comment states the original design: X rides every plan because the server cannot tell an X ability from its siblings.
   The cost of that design is real (the 31% above); the fix needs the engine's answer, not a text match.

2. **`--penalty 0` is a reward change.**
   The audit files it under bugfixes "consistent with ADR-0062/0072".
   ADR-0062 closed deterrence as an axis of work.
   The big run's launch line carries `--penalty 0.02` ([ADR-0123](../decisions/ADR-0123-big-run-launch.md)), and `rl.py`'s help text calls a change of lambda an RL-chain boundary.

3. **The fork's Stage A is two boundaries.**
   The bridge isolation changes how the Monte Carlo opponent plays: its rollouts get a heuristic in the Anvil seat where they had a seat that always passed.
   The 0.5099 figure and every `--mc-frac` game sit on the far side of it.
   The mode gate's quiet probe moves the mainline RNG stream at every served mode window.
   The fork document notes the first; neither document calls either a boundary, and the Anvil document's verdict says "zero-boundary".

4. **The merge would have removed M13's control.**
   The Python commit changes about ten things in the trainer and `m13_arms.sh` at once.
   No run after it compares with `m13-control` or `m13-nosearch`.
   M13's question is what in the recipe produces the gain; these changes are candidate answers and belong in arms.

5. **The loss renormalisation changes scale.**
   Distillation, allocation and soft terms move from a mean per segment to a mean per trajectory.
   A loop recalibrates its shares at iteration 0, so a new loop is safe.
   A weight carried from an older loop would be mis-scaled.

6. **Optimizer state has no pruning.**
   `opt_state.pt` is about twice the checkpoint, near 580 MB, and every iteration directory keeps one.
   A searched arm ran 65 iterations in 84 loop hours, so about 38 GB; search off is on course for about 180, so over 100 GB.
   (The split's commit message and this session's devlog say "near 95 GB" from an assumed 165 iterations; these are the figures.)

7. **Loading the ability table creates a serving obligation.**
   Today a server without the table plays the same games, because the projection is zero.
   Once it trains, every reader has to serve the table.
   `cand_abil_proj` also falls in the default learning-rate group; [ADR-0069](../decisions/ADR-0069-d4-read-adjudication.md)'s arithmetic for a fresh parameter family argues for a group of its own.

8. **The flag's predicate was wider than its consumer's.**
   The audit's fork patch wrote `"x":1` from `hasXInAnyCostPart`.
   `tryApply` acts only on an X in the mana cost.
   An option flagged for a non-mana X would have an X sampled, recorded and ignored.

9. **The audit's documents do not follow the project's conventions.**
   They sit in `docs/design/` and `docs/Development/` as plans with DONE marks, mix state with record, and carry no ADR.
   Their Tier 3 proposes pruning the standing rules to 15–20 and trimming the style guide; both are the user's decisions, and the rule prune already waits on the user's read.

## What the audit got right that deserves credit

- The dead ability path and the frozen surface heads were both invisible to every existing guard. Zero-initialized projections and `load_compat` hid them.
- The Monte Carlo finding explains [ADR-0135](../decisions/ADR-0135-m13-build3-arms.md)'s open item 5, carried as open since Build 3's launch.
- The two invariants it proposes are sound: every training change shows nonzero gradient on every expected path, and every served head has a named training owner.

## The split

The original branches are untouched.

| Branch | Base | Commits | State |
|---|---|---|---|
| `audit-land-now` (`.claude/worktrees/audit-land-now`) | main | One: voided games leave four reports' denominators; entropy by head and gradient norms by parameter family in `metrics.jsonl`; the search-row prefix fix | Tests and lint pass. Lands at search off's close. |
| `audit-arms` (`.claude/worktrees/audit-arms`) | `audit-land-now` | Eight, one per change: the X mask; the ability table in the trainer; online surface distillation; optimizer state across iterations; loss weighting; the allocation head's detach; two model corrections; `--penalty 0` | 61 tests pass. No training run. Unscheduled. |
| `audit-stage-a-split` (fork, `../forge-audit-split`) | `68168fb214` | Four: the copier's crew and saddle remap; the Monte Carlo bridge isolation; the mode gate's quiet probe; the per-option X flag | Compiles (all six modules and test sources, 11-27 18:09). Tests and forkcheck not run. |

Changes this review made to the audit's code:

- **The X mask keys on the field's presence.** The fork writes `"x"` on every option, 0 or 1. An option without the field reads True, so on the pinned jar every path is as on main.
- **The flag and the realizer share one predicate**, `CastPlanRealizer.readsX`.
- **The voided-game fix covers `baseline_reads.py` and `m13_precon_report.py`** as well as the audit's two scripts.
- **The audit's one test file is one file per change**, so a commit can be dropped alone.

The telemetry in `audit-land-now` is logging only: the summed entropy is the same expression in the same order, and the gradient norms read existing gradients.

## Still unverified in the split

- The fork's two new tests and forkcheck have not run.
- The copier remap has an untested case. A crew member that left the battlefield since crewing is not in the card map; `find()` prints "Couldn't map" and returns null, and `IEntityMap.mapCollection` adds what it is given.
- The model-corrections commit is not proven identical on the game path. The attack-target self mask changes sampling wherever the head put mass on the attacker.
- No commit on `audit-arms` has run in a loop. The online surface distillation in particular has only its unit test.

## Ideas the review prompted

Routed by name to the next scoping session; none is scheduled.

- **A dead-parameter census in the analysis battery.** A per-family weight diff between consecutive checkpoints, flagging zero norm and zero drift. It is about thirty lines, and it also shows `pay_*`, `plan_*`, `sched_*` and `opt_*` at zero drift over the control. Some of those are retired by design; the census would make each one a stated fact.
- **A guard on the server's fallback count.** 33,503 fallbacks per iteration sat in `counts.json` from the day the Monte Carlo opponent entered. A nonzero count per tag should raise an alert.
- **A capability declaration from the jar.** Field presence works for one flag. A declared list in the game header would scale to the observation changes the audit proposes.
- **A paired read of the Monte Carlo opponent, old jar against new.** It measures how much the passing seat handicapped the opponent, and it belongs with pin 6's reference opponents, which wait on the user.
- **Order the observation proposals by measured blind-spot size.** The audit bundles about twelve representation changes into one boundary. A census of how often each missing field would have differed, on existing stores, would rank them first.

## Routing

- `audit-land-now`: merge at search off's close, beside `m13-tail-log`. The two merge cleanly with main and with each other.
- `audit-arms`: arms after a fresh control on the new jar, on the user's word.
- `audit-stage-a-split`: tests and forkcheck when the box is free; the Monte Carlo isolation needs an ADR when it becomes a pin.
- The audit's Tier 2, Stage B and Tier 3: the next scoping session, unverified.
- The session's narrative: [devlog 2026-11-27](../devlog/2026-11-27.md) and the [M13 running record](../design/m13-running-record.md).
