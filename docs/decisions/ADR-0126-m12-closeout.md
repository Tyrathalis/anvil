# ADR-0126: M12 closeout — training scale works: the big run moved the network +9.46pp over its era reference, network alone; whether search teaches is unattributed and the recipe is not pinned; that question opens M13

- **Date:** 2026-11-16
- **Status:** accepted (the user's adjudication, 2026-11-16: "the big run proved that additional training scale helps, but suggests that we haven't yet pinned down a precise recipe. We don't know whether search helps, and we don't know whether we have the right ratio between data and training, but we do know that significantly increasing the training scale did push the winrate significantly higher.")
- **Design-doc anchor:** m12-plan.md (the doc of record, closed by this ADR); anvil-design-v2 §3e (search as the behavior policy), §4 (the critic), §6 (the loop); [ADR-0101](ADR-0101-architecture-review-m12-recharter.md) (the charter), [ADR-0123](ADR-0123-big-run-launch.md) (the big run and its 11-16 close)

## Verdict

**M12 closes positive on scale and open on mechanism.** The milestone built the complete structure the charter asked for and ran it once at scale. The big run's result, `big-run/iter-405`, plays at **0.6214 ± 0.0069** against Forge's heuristic on 5,000 fresh-seed games, network alone, **+9.46 ± 0.77pp** paired over the era reference `d6-run11/iter-019`. Head to head it scores 0.5865 ± 0.0057 against its own warm start. This is the project's largest measured strength gain, and the first one large enough that the gate resolves it many times over.

Three things are known.

- **More training at scale raises strength.** The run played 246,720 games in 840.8 wall hours, against about 10K games per run before M12 (ADR-0101 finding 2). The confirmed paired margins rose at each promotion: +4.22, +6.32 and +9.46pp at segments 1, 3 and 4.
- **The network is strong without search at play time.** The charter's first kill condition was with-lookahead climbing while network-alone stayed flat. It did not fire: network-alone carried the gain, and lookahead adds 3.2pp on top at `iter-405`.
- **The loop runs unattended for weeks.** No kill rule fired. Every stop was an infrastructure event, and each one left a fix in the launcher, the guards or the server.

Three things are not known.

- **Whether search teaches.** No search-off arm exists at this scale. The search acts on 0.4% of bridged windows, and its distillation gradient on the trunk is 0.005 against the policy gradient's 0.07 (iteration 425). The run cannot separate "search teaches" from "scale works" (the 11-09 design review, finding 1).
- **Whether the ratio of data to training is right.** The training step is 422 s of a 4,600 s iteration at a `kl_mu` far under its guard. More learning per game is untested.
- **Whether the gain continues on this recipe.** Segment 5 moved nothing the reads can see (`iter-513` is −0.78 ± 0.73pp under `iter-405`). That is about 2 SE under the earlier segments' mean gain, not a plateau finding: only segment 4 separated from its predecessor on its own.

The value head is the milestone's weakest product. Its holdout ranking fell from 0.48 to 0.33 over the first 300 iterations while its anchor memorized the fixed bank ([ADR-0124](ADR-0124-anchor-bank-refresh.md)). The transplanted head held 0.45 through segments 4 and 5 and did not improve. Two boundary reads said the leaf is not what caps strength at the 1pp level.

## The done-when clauses

| # | Clause | State |
|---|---|---|
| 1 | The engine bundle as one forkcheck-proven boundary; veto at apply ≈ 0; the game-time tail cut; the budgeted directive | Met, with a residual. The mask is exact for payability and for targets ([ADR-0102](ADR-0102-m12-build0-pins.md), [ADR-0122](ADR-0122-union-target-mask.md)). Vetoes are 6.5% of generation attempts and 1.5% of first attempts in the confirm read, not zero. |
| 2 | The value head's one-ply and state ranking move under Build 1 | One-ply met (0.277 → 0.397 ± 0.019). The state bar of 0.50 was missed at 0.375 ([ADR-0103](ADR-0103-m12-build1-value-head-and-build3-enumerators.md)). |
| 3 | The day-zero paired read adjudicated | Met: in-band ([ADR-0104](ADR-0104-m12-build2-acting-rule-and-dayzero-read.md)). |
| 4 | Every §3d′ family answered by the model under search | Met: six surfaces from one option-set decoder ([ADR-0108](ADR-0108-m12-build3-closeout.md)), then the allocation head and the target decoder ([ADR-0112](ADR-0112-m12-build4-allocation-head-served.md), [ADR-0116](ADR-0116-player-target-positions.md)). Learnable stops are unbuilt. |
| 5 | The representation completions and the format readiness | Met ([ADR-0111](ADR-0111-m12-build4-opening-targets-surface-site.md), [ADR-0120](ADR-0120-constructed-model-row.md), `format-onboarding.md`). The onboarding smoke on played Constructed games is still owed. |
| 5½ | The shakedown on file | Met ([ADR-0115](ADR-0115-m12-shakedown-scoping.md); the settings pass, [ADR-0119](ADR-0119-value-function-first-before-the-big-run.md)). |
| 6 | The big run inside a four-to-six-week envelope, with its series on file | Met at five of six segments, closed at the user's call ([ADR-0123](ADR-0123-big-run-launch.md), 11-16 addendum). |
| 7 | Closed by the standard 2,000-game read | Met: 0.6210 ± 0.0108 at segment 4's close, confirmed on 5,000 games. |
| 8 | The closeout routes by name | This ADR, below. |

## Decisions

1. **M12 closes.** The checkpoint of record stays `big-run/iter-405`. The recipe of record stays as written in CLAUDE.md and is the control arm of whatever M13 runs first.
2. **M13 is not chartered here.** Its first question is the one this milestone leaves open: what in the recipe produces the gain. The charter is drafted after the three measurements in decision 3 and after the routing below is re-read against them.
3. **Three measurements run before the M13 scoping.** None is a training run.
   - **The offline gate.** On stored searched windows, the search's option ranking against K=8 rollout truth, split acted and un-acted. Near chance on the un-acted rows and the soft-target arm is not run.
   - **The ladder of own checkpoints.** The warm start, `iter-099`, `iter-301`, `iter-405` and `iter-513` head to head. It becomes the scoreboard beside the heuristic read.
   - **The search's wall cost on the current recipe.** It was 2.1× per game at Build 2 and has not been re-measured. It sets how many more games a search-off arm plays at equal box time. It is a calibrated timing and runs on a quiet box.
4. **The documentation pass runs now**, beside the first two measurements. Its routed items are in the table below.
5. **The stale-data pass runs with it.** `data/training/big-run/` is kept whole until the M13 arms' start is designed. Deletions wait on the user's sign-off of the kill list.
6. **[ADR-0125](ADR-0125-value-head-track.md) stays proposed.** It is a candidate center of M13, judged on advantage variance as well as on the leaf.

## Routing by name

First-pass dispositions. The user re-reads this table at the M13 scoping, after the three measurements; an item marked for the scoping is scheduled or re-deferred there with a reason.

**To the M13 scoping, as candidates for the milestone's work:**

| Item | Source | Note |
|---|---|---|
| Three arms at equal box time: the recipe of record, search off, soft targets | 11-09 review | Sized first: a week-long arm moves about 1.5pp at the run's slope and a 5,000-game paired read resolves 0.7pp. |
| More learning per game (the training step's share of the iteration) | 11-09 review; the user, 11-16 | The data-to-training ratio; one paired arm, read against the 10-28 `kl_mu` trip. |
| The value-head track: the truth stream, the critic, the student; the critic as the advantage baseline; a λ < 1 return arm | ADR-0125; 11-09 finding 2 | The amortized advantage head (ADR-0119 item 4) is folded in. |
| Learnable stops | 11-09 review | Passes are two-thirds of bridged windows. |
| The engine benchmark (the Rust and Go engines) and the Rust subset engine's re-pricing | 11-09 review; plan | A one-day benchmark; the port bet's condition (throughput binding) is met. |
| The short 60-card format as the research testbed; the Pauper testbed (fork G) | 11-09 addendum; plan | More outcome bits per box-hour. Two formats in one network is an unmeasured bet. |
| Training on a second format (fork I) | plan | Behind the testbed decision. |
| Shipping the network (the Android ship; `iter-405` in the playable build) | plan; 11-09 order | Independent of the research order; the user's call when. |
| The belief sampler for determinization | 11-09 review | Its place depends on the arms: a deployment-time project if search leaves training. |
| The trunk-capacity probe (a 2× trunk on outcome prediction over the stores) | 11-09 addendum | No capacity milestone without it. |
| Pool growth | 11-09 addendum | After a held-out-cards read and after signal per game has risen. |

**To the next boundary (the first fork or learner change M13 makes):**

| Item | Source |
|---|---|
| The `CensusRun -certify` and `PayDirective` deletion and the `payment-evalset-v2` re-certification | ADR-0117 |
| The learner's memory: the worker RSS profile, the allocator settings, the decode change, the chain's halved-workers retry | the user, 10-17 |
| The loop config and model prune (the retired plan, schedule, payment-label and sequence machinery) | 11-09 review |
| The NullPointerException crash (11 and 13 games per 5,000 in the 11-15 reads) | running record, 11-16 |
| The oversize game's source | running record, 11-10 |
| The tripwire's drop-rate drift across the run | running record, 11-12 |
| `iter-513`'s tripled unpayable proposals and its self-target rate (0.243 against 0.209) | running record, 11-16 |
| The residual vetoes (done-when 1) | this ADR |

**To the documentation pass (now):**

| Item | Source |
|---|---|
| The standing-rules prune (each rule about two lines, the detail in its ADR) | the 09-23 fluency review |
| The design doc's §3d′ ledger cut to the current coverage table; §13 | the 09-23 fluency review |
| `/consolidate-memory` over the entries that repeat CLAUDE.md | the 09-23 fluency review |
| The dated history that remains in code comments | the 11-09 documentation review |
| The field guide, the canonical register, the quickstart, `docs/ops/`, the map | the wrap-up checklist |
| The quickstart's onboarding smoke on played Constructed games | the 09-23 fluency review; needs box time, so it may follow the pass |

**Re-deferred, with the reason:**

| Item | Reason |
|---|---|
| A Spellbench entry | Its condition stands: after a format and a card chunk have been added and tested. |
| An LLM opponent seat as a diversification corpus | Beside Spellbench; $600–1,800 and days of wall per 2,000 games buys nothing until the recipe is pinned. |
| A learned, in-model ability encoding | Low priority (the user, 10-23); belongs to the from-scratch recipe-trimming stage. |
| Learned dynamics as a search accelerator | A possibility, not a plan; it needs the learned encoding first, and search's place in training is itself open. |
| The skill token and human-shaped levels | Needs human games. |
| Ponder-time search | Follows the arms' decision on search. |
| Match play; Tutor and Mentor as products | Product surfaces; after the recipe is pinned and the network ships. |
| Trackio logging | User-queued 08-13 as a potential item; not started. |

## Consequences

- **The plan doc is historical.** `m12-plan.md` and its running record are closed. The running record takes this session's entries and no later ones; M13's record opens with its plan.
- **Until M13 opens, the Now block is the live plan.** It names the three measurements and the documentation pass.
- **The era reference changes role.** `d6-run11/iter-019` was the big run's reference. M13's scoreboard is the ladder plus the heuristic read against `iter-405`; its reference and bars are pinned at the scoping.
- **No standing rule is born here.** Two candidates go to the prune for the user's read: an attribution control arm at the scale of any run that tests a mechanism, and arms sized against the read's resolution before they are ordered. The second is the existing power-statement rule applied to arm length.
- **Carried assets.** The search directive and its seven served surfaces; the loop under the finding-4 supervisor, with its guards, the memory watchdog and the per-iteration arm reads; the union target mask; the head-to-head read (`scripts/h2h_read.py`, `--seat-ckpt`); the two frozen holdouts (Build 1 and the run-distribution bank); the big run's stores and its five segment checkpoints.
- **Hazards carried.** A fixed truth set is memorized inside a run and goes stale as the policy moves (ADR-0124). Offline distillation toward the search lost up to 47pp with the dose ([ADR-0111](ADR-0111-m12-build4-opening-targets-surface-site.md)), which is the soft-target arm's known risk. Numbers from this era are not compared with earlier eras.

## Addendum (2026-11-16, the documentation pass): routing additions and one correction

- **Correction: the gate is not offline.** Decision 3 says the offline gate reads stored searched windows. A stored window of a model-served game cannot be reached again, and no tool forks from one. The gate is a live read with an end-of-game leaf on a sample of searched windows. Its draft design, with the ladder's and the wall cost's, is [m13-prescoping-measurements.md](../design/m13-prescoping-measurements.md). ADR-0106's priority-slot calibration is its closest prior and its step 0.
- **Added to the M13 scoping.**
  - Whether the model's answer is served at the generic target choosers (`chooseTargetsFor`, `chooseNewTargetsFor`, `chooseTarget`). The design doc's coverage table marks it not established.
  - The low-weight untraced callbacks (card piles, shield division, play or draw, opening-hand Leylines, the resolution-time confirms). They were routed to "after the big run" and are heuristic-answered and untraced.
  - The late-payability scan that the residual vetoes point at (ADR-0005), named in the canonical register.
- **Added to the next boundary, from the 11-09 infrastructure survey's open findings** ([infra-survey-2026-11-09.md](../ops/infra-survey-2026-11-09.md)): the phone path (`ANVIL_NOTIFY_CMD` unset, no file fallback); a memory guard for the generation phase; the multi-row form of the casts, share, entropy and veto guards; the standing watcher's retirement (`anvil-watch.timer` still ticks, old scripts still register); a pause line recording `done`; the watchdog choosing its kill set by command-line substring; an `anvil.runs stop` verb; the two remote-control units; the finding-4 leftovers (pid checked by number only, a reboot without `pause` reading `failed`). Two stale docstrings ride with them: `anvil/runs.py` ("no timer") and `anvil/training/vram.py` (the retired stall alert).
- **The user's calls, raised by the pass.** One pass over the roughly 410 dated code comments, two thirds of them in launch scripts for closed runs. The quickstart's reorganization from §7 on for the outside reader. The stale-data decisions in [stale-data-pass-2026-11-16.md](../ops/stale-data-pass-2026-11-16.md).
- **The standing-rules prune kept all 110 rules and retired none.** The file went from 41.3 KB to 28.5 KB against a 25 KB target; the remainder is rule text and link paths.

## Addendum (2026-11-16, later): the user's direction for the M13 scoping

- **M13's likely shape.** Testing other training setups to find what works best, opened by an upstream merge. The merge and its opponent question are scoped in [m13-upstream-merge-scoping.md](../design/m13-upstream-merge-scoping.md); three points there are pinned.
- **A coverage goal joins the M13 candidates: a pool wide enough that the model is worth serving publicly.** The user's framing: a capability space in which the model's competence can be described, such as every card in the Commander precons or one Modern season, and the question whether the model can be the best AI player in the world at preconstructed Commander. Not every card Forge supports at once, and after a couple more passes on the training setup.
- **What the precon space is, counted from Forge's own deck files** (`res/quest/commanderprecons` at upstream `0f82b4f469`): 184 decks and 6,543 unique cards. 591 of them are in the current pool of 1,701, so the full space adds 5,952 cards, about 3.5 times the pool. One release year is 300 to 1,600 unique cards; the newest two years together are 2,120. The median precon is 23% covered by today's pool.
- **What it changes in the routing above.** "Pool growth" and "a Spellbench entry" stop being separate deferrals: the precon space is a named target for the first and a natural scoreboard for the second. The held-out-cards read stays the gate, and precon decks are a ready source for it: they are legal decks built mostly from cards the network has never seen.
- **One scope question it raises.** Precons are built for four-player Commander. The project's scope is one-on-one under the 40-life ruleset ([ADR-0018](ADR-0018-ruleset-scope-clarification.md)). A claim about preconstructed Commander has to say which, and multiplayer is a different research problem.
