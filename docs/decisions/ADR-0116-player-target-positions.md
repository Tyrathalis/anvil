# ADR-0116: The player-position convention — the cast-target decoder's mixed label (self-first rows, registered-index labels), its measured cost, and the fix

- **Date:** 2026-09-21
- **Status:** accepted (user: "shut down the run, I don't want us proceeding with something known-wrong"; "allow the model to identify individual players, but not full multiplayer now")
- **Design-doc anchor:** §1 (encoder: perspective invariance), §3 (the CastPlan decoder), §9 (bridge)

## Context

Kryptic (Discord, 09-21) traced his mono-red mirror's 23.5% BC win rate to burn spells aimed at
his own face and found the cause: raw trajectory refs name players by **registered seat** (`pi`),
the model's player rows are **self-first**, and the dataset label copied `pi` straight into the row
position while the bridge decoded the pick back as a registered index. From seat 1 both are swapped.
His fix took the mono-red BC mirror from 23.5% to 47.1% and own-face burn from 24% to 0.4%.

**Our tree had the same seam, and we had seen half of it.** The 07-14 devlog records catching the
convention split when the combat heads landed: the combat player targets were made self-first and
converted through the seat list at both ends, and a parity test pins that. The target decoder was
left on "absolute registered index" with the note *"both are internally consistent train↔serve"*.
That was the wrong test. There are three coordinate systems, not two: the label, the decode, and
**the model's option rows**, which `player_key(batch["players"])` builds from the self-first player
features. Label and decode agreed with each other in registered coordinates while indexing rows
laid out in self-first coordinates. The model has no seat feature (the encoder is perspective-
invariant by design), so "target the opponent" was a coin-flip label across a corpus with both
seats represented, and the policy gradient on those windows was noise. Kryptic's model sat at
13–24% self-targets because its turn and active-player globals leak the seat; ours has the same
globals, but the audit below says it never learned the XOR.

**Measured on the b4post network-alone read** (`build3-surface-read-b4post` on arm, 2,000 games,
the model's seats vs the heuristic's in the same games; `scripts/player_target_audit.py`):

| seat | player-targeted casts | targeted itself |
|---|---:|---:|
| model, registered seat 0 | 322 | **46.6%** |
| model, registered seat 1 | 367 | **45.8%** |
| heuristic, seat 0 | 437 | 11.2% |
| heuristic, seat 1 | 569 | 12.1% |

The heuristic's 11% is the legitimate self-target share (draw, ramp, "target player" effects the
caster wants). The model's 46% from either seat is the coin flip, symmetric because from seat 0 the
50/50 head decodes half wrong directly and from seat 1 the swap flips both halves. Exposure in
this pool: ≈ 1.1% of the model's casts, ≈ 0.34 player-targeted casts per model seat per game —
against the heuristic's 1.9%: **the model learned to avoid the class** (half its attempts were
wasted). The search inherits it (a candidate burn or wheel is valued at a leaf where its target was
a coin flip). And a third, possibly larger, exposure: the target decoder has **no legality mask on
the player rows**, so a self-pick on a spell that cannot target self is a realizer veto in the
`no_shape_fit` class — 93% of the void copies ADR-0114 attributed to the decoder's coverage bound.
Kryptic's `no_shape_fit` vetoes fell 77 → 16 after his fix. Whether ours fall is the first thing the
corrected build's read measures.

The shakedown (ADR-0115) had launched 90 minutes earlier from the affected build; it was paused and
its partial iteration discarded.

## Decision

1. **One convention, one helper** (`anvil/encoder/transform.py`): `PLAYER_TARGET_CONVENTION =
   "self_first_turn_order_v1"`, `player_seats(perspective, n)` = self first, then the other seats
   in **turn order after self** (registered order rotated to the deciding seat), and
   `player_target_position(pi, perspective, n)`. Every model-side player position — the player
   feature rows (`assemble`), the dataset's cast-target labels, the featurizer's `seats` aux, the
   combat heads' seat list — goes through it; registered indices live only in the raw records and
   the engine. For two players the order equals the old `[self] + registered order` form byte for
   byte (the served builds' features are unchanged); for n ≥ 3 the rotation keeps the encoding
   invariant under seat permutation, where registered order after self would leak the seat through
   the opponents' order. **This pins the model's ability to identify individual players for any n;
   multiplayer itself (harness pairs, the n-seat reward, Ante's certification) stays routed to the
   closeout.**
2. **The fix at both ends**: `dataset.py` converts `ref["pi"]` through `player_target_position`;
   `server.py` decodes the pick through `decode_player_ref(pos, aux["seats"])` (out-of-range
   raises rather than resolving a dangling ref). The RL sampling records already carry model
   positions (`mu` unchanged); the fork is untouched (it indexes registered players).
3. **The convention pinned in every checkpoint** (`config["player_target_convention"]`, written
   by `train.py`, `rl.py` and the refit); the server and the RL loader **refuse a different one**
   and **warn on a legacy checkpoint** that records none (its target head learned the mixed label
   and is served through the corrected decode, still a coin flip, until refit).
4. **The refit** (`anvil/training/target_refit.py`): the served build `m12-build4-e1a` with ONLY
   the target decoder's parameters (`tgt_query`, `tgt_key`, `player_key`, `stop_key`, `slot_emb`,
   1.06M of 71.7M) retrained on heuristic-labelled sv=3 windows under the corrected labels — the
   two `b2-heurarm` mirror stores (2,000 heuristic-vs-heuristic games), 3,000 player-target
   windows + an equal number of other targeted casts (so the entity part does not drift), a 1-in-5
   holdout, per-class accuracy before / after (entity, player-self, player-opp, STOP) and the
   predicted-class mix on player slots. Output `data/training/m12-build4-e1a-tgt/last.pt`; the
   alloc head and its fit record ride along unchanged. **The read**: the paired network-alone read
   (e1a vs the refit build, 300 per seat, 24 × 2) + this audit on both arms (the model's self-target
   rate is expected to fall from 46% to the heuristic's ≈ 11%) + the mainline veto census by class
   (`no_shape_fit` before / after). Nothing broke + the audit's fall → the refit build becomes the
   day-zero build and the shakedown relaunches from it (ADR-0115 amended: the day-zero build).
5. **The instruments made standing**: the player-target audit is a row of the eval battery (the
   model's self-target rate vs the heuristic's in the same games; an anomaly when > 2× on ≥ 100
   casts); `tests/test_player_target_indexing.py` pins the helper, the round trip label → position →
   decode → the same registered player from every seat for n = 2, 3, 4, the documented seat-1
   failure of the old decode, and the checkpoint check.

## Consequences

- **Standing rules born here** (→ standing-rules.md, engine / fork / data hygiene): (a) *a
  convention is checked through the model's row space, not label↔decode agreement* — for every
  head with a player or seat reference, a permutation test over the whole path (swap the registered
  seats; the decoded engine object must be the same object); (b) *every read reports the
  target-sanity row* (self-target rate vs the heuristic's); (c) *a checkpoint records its label
  conventions and a loader refuses a mismatch*.
- ADR-0114's coverage bound is re-read on the corrected build: if the `no_shape_fit` class shrinks,
  the Build 5 risk statement shrinks with it (an addendum there).
- ADR-0115 amended: the day-zero build = the refit build; the shakedown's arms restart from it.
- Routed by name: the "seat-symmetry line" in `final_read` (win rate by registered seat — catches
  Kryptic's shape, not ours; cheap); the surfaces' player candidates are enumerated lists and
  unaffected (checked); the legality mask on the decoder's player rows (a strength item: an
  illegal self-pick should be impossible, not vetoed) → the Build 5 queue.
- Community: Kryptic credited; the draft reply posted by the user 09-21.
