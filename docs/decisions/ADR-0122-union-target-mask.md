# ADR-0122: The union target mask — the fork lists each priority option's legal targets, the decoder points only inside them

- **Date:** 2026-10-04
- **Status:** accepted (built 10-04; the first tip's forkcheck PASSED 20:22; **the agreement check CLEARED on the re-read 22:47 — 0 of 23,647 heuristic-chosen targets outside the mask** on fork `e412dbb24d`, forkcheck `run-20261004-tgtmask2` 499/500 PASS 22:03 = the pin; the paired read launched 22:55, its verdict an addendum)
- **Design-doc anchor:** §3 (the CastPlan decoder: "each step hard-masked by engine legality"), §9 (the bridge: masking is construction — [playercontroller-override-plan.md](../design/playercontroller-override-plan.md)); [bridge-protocol-v0.md](../design/bridge-protocol-v0.md) `TargetPlan` (indices into the legal-candidate list); amends [ADR-0116](ADR-0116-player-target-positions.md) (its player-row half lands here) and extends [ADR-0005](ADR-0005-d3-label-mask-timing-legal.md) (the mask is a superset of the expert's picks, proven on a corpus, never argued)

## Context

The cast-time target decoder was a free pointer. Since M1 it pointed over every entity row and
every player row with a padding mask only; the realizer vetoed illegal picks (`no_shape_fit`,
`added < min`, a ref on a non-targeting ability) and `-reask` dropped the vetoed ability for the
rest of the window, so an ability got one try at its targets per window and the model learned each
card's targets across games under the 0.02 veto penalty. The design named a mask from the start
("each step hard-masked by engine legality"; the override plan's invariant; the protocol's
`TargetPlan`), and the M1 label extractor recorded the heuristic's injected targets as entity refs
because they never surface as a callback (ADR-0004) — the free pointer was the staged form that was
never promoted. Kryptic's #ai-plotting thread (10-02) put numbers on it: on the resolution read's
alloc arm (5,000 games) `no_shape_fit` was 4,828 vetoes over 361 abilities, ≈ 3% of cast attempts,
half of it conditional targets the pointer cannot see (mana value ≤ 3, counter MV 2, power or
toughness ≤ 2, nonblack) and abilities that almost never fit (Chthonian Nightmare 60 vetoes vs 0
casts). The user routed it pre-big-run on 10-02 as a correctness item, behind the Spider-Man 2099
option-mask fix (landed `9c589c1ced`, 10-03): the go/no-go is the agreement check, and it drops to
after the run if the implementation fights back.

## Decision

1. **The fork lists the union.** `TargetUnion` (forge-ai, `forge.ai.anvil`) enumerates, per
   priority option, the union over the sub-ability chain's targeting nodes of
   `TargetRestrictions.getAllCandidates` — players, then the cards of the node's zones, the same
   read the out-of-cast target surface uses (ADR-0109 / ADR-0111) — plus the stack entries the
   node may target (`getAllCandidates` never lists abilities on the stack; the engine's own
   `getNumCandidates` loops the stack). Every node's targets are cleared and restored around the
   read and the scratch RNG is armed, so the option is left as found and the game's randomness
   never moves. The field rides the `opts` entry the observation writer already builds
   (`Obs.decPriority`): `"tg":[{"e":id},{"pi":seat},{"e":hostId,"stk":1}],"tn":<summed
   minimum>[,"tz":1]` — `tz` = a node with a minimum of one or more has no candidate, so the
   option cannot fit whatever the model picks. A non-targeting option carries `"tg":[]` (STOP
   alone is legal: `tryApply` refuses any ref on it). `peekPriority` (search leaves, the
   allocation ask, certify arms) is unchanged — those windows decode no targets.
2. **Exactness over coverage: unmasked where the scan cannot know.** A node enumerated with its
   parents' picks empty passes every restriction that reads earlier picks (another target, same
   controller, different mana value, total-mana-value caps, divided amounts), so the union
   OVER-approximates there and the realizer stays the backstop — the arrangement the 10-02 routing
   named. Where clearing makes the engine UNDER-approximate — `TargetsWithRelatedProperty`
   (`canTarget` returns false until a parent target exists), a controller or shared type defined
   by a parent's pick, `TargetingPlayerControls`, and any `ValidTgts` / `TargetMin` / `TargetMax`
   that reads X under an X cost (the scan reads X as 0) — the option is declared unmasked
   (`"tg":null,"tu":<reason>`) rather than given a wrong set. A mask that excludes a legal target
   is the one failure the agreement check must never see; coverage is counted, not assumed.
3. **The decoder points only inside the chosen candidate's set.** One Python builder
   (`anvil/encoder/target_mask.py`) serves the featurizer and the loader: per candidate, the
   union of its collapsed options' refs mapped to entity rows (a dedup row is legal when any
   member is) and to the ADR-0116 self-first player positions, STOP always open, a ref the
   information-set transform hid dropped, PASS and any candidate with an unmasked member open
   everywhere. `AnvilNet._tgt_pad` closes the complement in forward (the label's candidate) and
   act (the sampled choice) through the same function, so the mu recompute sees the distribution
   the pick was sampled from; absent the field the decoder is the pre-mask decoder exactly.
   Collate re-bases the player block and STOP onto the padded width. The mask is absent for tuck
   and every non-priority task.
4. **Additive, not a boundary.** Older stores have no `tg` and read unmasked, like `ak` before it
   (ADR-0105); the server records the rule it applied in the mu row (`tm`: masked / pruned) and
   the RL loader re-applies that rule, so a store sampled by an older server recomputes unmasked.
   `--no-target-mask` serves the pointer unmasked (the paired read's control arm);
   `--prune-unfit` drops `tz` candidates from the choice (default off; a serve rule, never a
   label rule; not composed with sched binding). `-Danvil.tgtmask=off` withholds the field on
   the fork. The field is recording-only and not in the forkcheck digest; the proof is still the
   ADR-0025 forkcheck, run before the jar serves anything.
5. **Fold-in: the surface decoder's player key.** `surface_fields` stored a player option's
   REGISTERED seat and `_surface_decode` gathered it from the SELF-FIRST player rows, so from seat
   1 a player option carried the other player's features — the ADR-0116 class (three coordinate
   systems) on the out-of-cast surfaces; decoding is by option index, so the engine applied the
   right target and the representation was swapped. The builder now maps through
   `player_target_position` when given the perspective (every caller passes it).

## Pre-registered gates (10-04; the running record carries the launch entries)

- **The forkcheck** (`run-20261004-tgtmask`, the standing 500 seeds against the 09-16 merge
  baseline): identical but for the standing seed 20260969 = PASS; the pin moves to
  `5b54fbe6ef`. Any other mismatch ⇒ a boundary, and the field is not recording-only after all.
- **The agreement check** (the go/no-go the user set): a fresh heuristic corpus on the mask jar
  (`tgtmask-agree`: 2,000 pool-pair games, every seat heuristic, obs + census on), ingested and
  run through `anvil.store validate`, whose ADR-0122 branch checks every heuristic-chosen target
  (the plan's root-chain refs — the decoder's label space) against the chosen option's set. The
  bar is **zero** targets outside the mask among masked options. An attributable miss class (one
  restriction family) is handled by declaring that class unmasked and re-reading once; a residual
  miss after that = the mask is not exact, and the item drops to after the big run. Unmasked
  options are counted by reason, not checked; a cast on a `tz` option is an error of the same
  rank. Mode targets (outside the label space) are counted, not checked.
- **The paired read** (`tgtmask-paired`, launched by the queue only on a cleared agreement check):
  `settings-stopgrad-t3e6/iter-019`, seed base 20261003, 1,000 games per seat, network alone, the
  decoder masked, paired game-for-game against the cast-mask read's arms (the decoder unmasked;
  raw 0.5405 ± 0.0111). FLAG at a paired difference below −1.0pp or beyond 2 SE either way; the
  census must show the `no_shape_fit` class fall. **The timing check** is this read's generation
  wall against the cast-mask read's 43 min on the same seeds and workers: the mask may cost at
  most 5%; a wall above 45 min flags the enumeration (routed to the writer's cost before it serves
  a run).

## Consequences

- The reference checkpoint's network-alone number must be re-read under the mask before it is the
  big run's bar: the launch ADR re-reads `iter-019` on the mask jar with the mask on (the paired
  read above is that number's first look).
- Standing rule (engine/data hygiene): a legality mask on a learned pointer is proven on a corpus
  — every expert-chosen label inside the mask, the bar zero — before it serves a run; where the
  engine cannot enumerate faithfully the option is declared unmasked, never given a wrong set.
- Routed by name: STOP masking by the chain's minimum (the surface decoder's picked/min/max idiom;
  changes the sampled support more than the pointer mask does — read after this one serves);
  `--prune-unfit` on (a separate paired read; the choice distribution changes); the
  `peekPriority` windows (search leaves) if a future surface decodes targets from them; the
  stack-reference ambiguity when two stack entries share a host (pre-existing in the ref idiom).
- ADR-0116's "the legality mask on the decoder's player rows" (routed to Build 5) lands here.

## Addendum 2026-10-04 (evening): the first agreement read missed, attributably; the re-read runs

The first read (store `tgtmask-agree`, 2,000 games) put 1,586 of 23,768 heuristic-chosen targets
outside the mask. Attribution (the running record, 21:08): modal spells (1,522 + ≈ 35 — the union
never walked a Charm's modes), stack-zone cards (Reprieve), energy X (Chthonian Nightmare),
parent-defined ValidTgts text (Searing Blaze), the heuristic's own engine-illegal picks (Explore
onto a shrouded creature, divided damage at a hexproof player), one stale label. Fork `e412dbb24d`
walks the modes, reads X in any cost part, tests the ParentTarget / Targeted text, lists stack-zone
cards, and marks engine-refused labels (`"ill":1`) so the validator counts the heuristic's illegal
picks apart — the bar stays zero LEGAL targets excluded, read mechanically. The re-read
(`tgtmask-agree2`, its own forkcheck first) is the pre-registered single re-read. Found beside it
and routed: 87 heuristic casts whose host the option scan never offered (King T'Challa's back face
from the command zone, Dargo's cost-reduced cast, X spells) — absent from a 300-game sample of a
pre-cast-mask store; a commander-zone unit test before the launch ADR.

## Addendum 2026-10-04 (22:47): the re-read clears the mask's clause; the unfit clause relaxed, by my call

Fork `e412dbb24d` (forkcheck PASS 22:03, the pin): **0 of 23,647** heuristic-chosen targets outside
the mask on a fresh 2,000-game corpus (`tgtmask-agree2`); 24,385 options unmasked by reason (X
23,714, parent-defined 671); 10 labels the engine itself refused counted apart. One cast landed on an
option flagged unfit — Cryptic Command with a stale bound mode below its Charm node — and the
pre-registration above ranked that with an outside target. The flag feeds only the default-off
`--prune-unfit`, so the paired read went ahead on the mask's clause alone (the queue's gate reads
that clause; the unfit count is logged beside it); the fix (`5bd040351f`: nodes below a Charm are
mode nodes) gets its forkcheck after the read, and the prune is verified on the next labelled store
before it is ever turned on. The user may overrule; the read is cheap to redo. The validator's exit
still fails on the option-mask class found beside the mask (57 heuristic casts the scan never
offered) — routed, not the mask's.

## Addendum 2026-10-04 (23:42): the paired read clears — the decoder serves masked

`iter-019` masked vs unmasked on the same seeds: **−0.61 ± 0.49pp** (t −1.25, 1,963 paired), inside the
flag; `no_shape_fit` 1,170 / 1,101 → 692 / 724 (−38%, both seats), every other veto class unmoved;
the generation wall 42.3 min against the 43-min reference (bar 45). The masked decoder is the served
decoder from here; `forge-tgtmask2.jar` (`e412dbb24d`) serves the next run. The first look at the
reference under the mask: 0.534 ± 0.011 raw. Routed from the census: the remaining `no_shape_fit`
share is the backstop's (cross-node refs, a STOP before the chain's minimum) — STOP masking by the
minimum stays the first follow-up; `--prune-unfit` stays off until the next labelled store shows
zero unfit casts under `5bd040351f`.
