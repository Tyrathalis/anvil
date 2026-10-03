# ADR-0119: Value-function-first before the big run — anchor, then the Ante re-measure and draw coverage, then corrected reads, then amortized advantages

- **Date:** 2026-09-24
- **Status:** accepted
- **Design-doc anchor:** §4 (value head), §7 (Ante), §6 (training pipeline); m12-plan Build order 4 (the settings pass) and 5 (the big run); ADR-0101 finding 1, ADR-0118

## Context

**The working hypothesis (user, 09-24): strength is hard to move because the game is noisy, so
the specific instruments that see through the noise are worth investing in before the big run,
which should get every chance to succeed.** The sharper form: noise is a testable hypothesis only
beside an estimator that removes variance without adding bias. If the corrected read shows a gain
the raw read hid, the noise story holds; if the corrected read is also flat, the loop is not
learning — and that is the thing to know before four to six weeks of box time.

What exists today, read this session, against each place noise enters:

- **Measuring strength.** The shakedown's 2,000-game reads run raw (`final_read.py --skip-ante`
  in `shakedown_chain.sh`); ± 1.1pp carries the full shuffle-and-draw variance. The Ante ledger is
  built and certified unbiased ([ADR-0014](ADR-0014-ante-certification.md)) but its reduction is
  critic-bound at ≈ 0.6% (corr(raw, ledger) = 0.08; [ADR-0101](ADR-0101-architecture-review-m12-recharter.md)
  puts it under 5%) against §7's promised three-to-four-fold; and the poison rule skips ≈ 69% of
  draw nodes because shuffles are not observable as decision records.
- **The training signal.** Advantages are V-trace on terminal outcomes with the policy's own masked
  head as baseline; the full-vis critic baseline exists as `--critic-ckpt` but ADR-0049 found it
  irrelevant to strength (variance reduction on an already-sparse signal); §7's amortized
  chance-node correction for training advantages is designed and unbuilt.
- **The head itself.** The trunk under it drifts off rollout truth on unanchored outcome targets
  ([ADR-0118](ADR-0118-value-head-drift-under-the-loop.md) and its 09-24 addendum: the head-swap
  read puts the whole Spearman loss in the trunk's representation).

All three cap at the same value function (ADR-0101 finding 1). One asset, anchored, unlocks the
measurement fix and the training fix together; built in any other order, each fix is built on the
weak critic it is meant to replace.

## Decision

The work between the shakedown's verdict and the launch ADR runs in this order, each step gated by
the one before:

1. **The value-anchor arm first** (ADR-0118 item 3, unchanged: a replay term on the Build 1
   state and leaf banks; bar: Spearman within one bootstrap SE of the day-zero 0.374 across the
   pass while network-alone is not worse than the un-anchored winner). The per-term trunk
   gradient-norm row in `rl.py` lands with it so the read attributes which loss moves the trunk.
   **Pre-registered escalation if the anchor misses its bar, in order:** a lower `--value-weight`;
   the value gradient stopped at the trunk (the head alone chases outcomes); a separate value
   trunk. Each is one arm of the settings pass; the ladder stops at the first rung that clears.
2. **The Ante re-measure against the anchored head**, the two standing post-critic steps ADR-0014
   named: `certify --from-ledger` re-aggregated (minutes), then values re-scored (≈ 96 min). The
   number of record is corr(raw, ledger) and the effective-sample ratio. **Draw coverage:** a
   shuffle event as a decision record on the fork, so the poison rule cleanses instead of skipping
   the rest of the game — a fork commit with its ADR-0025 forkcheck proof (behavior-identical on
   the game path; the record schema's addition is priced as a boundary question in that commit's
   ADR). ≈ a day of fork work.
3. **Corrected reads on the settings pass.** Every read that sets a bar reports raw and corrected
   side by side. **Pre-registered: the corrected number becomes the number of record only once the
   re-measure shows ≥ 1.5× effective samples** (a ≥ 18% cut in SE); below that the raw read stays
   the read of record and the ledger stays an audit. The launch ADR's power statement quotes
   whichever resolution is of record.
4. **The amortized advantage head** (§7's training-side correction) is **gated on step 2's exact
   ledger clearing the same 1.5× bar**; below it the head is routed, not built — a correction the
   exact ledger cannot make, the amortized one cannot either.
5. The launch ADR then states the power at the resolution of record, with the anchor's read as a
   launch condition (ADR-0118 consequence 1, unchanged).

## Consequences

- The settings pass grows by the re-measure (≈ 2 h box + a session), the shuffle event (≈ a day of
  fork work + a forkcheck) and, only if gated in, the amortized head (days). The big run's launch
  moves by about that; the user's stated priority is the run's chances over its start date.
- The shakedown's verdict is unaffected: its arms are compared raw against each other, as
  pre-registered (ADR-0115).
- No standing rule is born; ADR-0014's effect-size honesty rule and ADR-0118's audit-and-anchor
  rule stand. If step 3 clears its bar, the rule that reads of record run corrected is written
  then, with the measured ratio.
- Routed by name, to the post-run worktree: the anchor term (ADR-0118); the trunk gradient-norm
  row and `--swap-head` (ADR-0118 addendum); the shuffle decision record (fork); the corrected
  columns in `final_read.py` / `arms_report.py` reporting raw and corrected together; the amortized
  head (gated).

## Addendum 2026-10-03 — step 1 closed: the ladder stops at rung 2; the value-head recipe of record

**The ladder's outcome (the settings pass, 09-27 → 10-03, four 30-h cells from day-zero plus the
reads; running record 09-28 → 10-03).** The anchor at weight 0.5 held the Spearman and cost
−5.1pp (OUT). Rung 1′ (anchor weight 0.1) held the Spearman at 0.41–0.46 and cost −1.57 ± 0.67pp
on the 5,000-game paired resolution read — below the −1.0pp margin the user fixed before any game
(MISS; the bar's "not worse" clause had set no margin, which is the thing to fix in every future
bar). **Rung 2 — the value gradient stopped at the trunk — CLEARS:** Spearman 0.390 → a 0.45
plateau, every row above day-zero 0.374, and −0.47 ± 0.69pp vs the alloc read of record on the
same paired seeds. Rung 3 (a separate value trunk) is not needed.

**The value-head recipe of record for the big run (one line in the chain, `settings_pass_chain.sh`
arm `stopgrad-t3e6`):** the alloc recipe + `--value-anchor data/runs/m12-build1 --anchor-weight 0.1`
as a HEAD-ONLY term + `--value-stopgrad-trunk` (`AnvilNet.value_stopgrad`: the value head reads a
detached [STATE] read-out, so V-trace, the anchor and the distill carry's value BCE train the head
alone; `gn_v` = `gn_anchor` = 0 on every row) + `--trunk-lr 3e-6` (cards / assemble / trunk,
everything upstream of the detach) + `--value-head-lr 1e-4`. The two lr groups are part of the
recipe, not tuning: rung 2's first cell at the trunk lr of 1e-5 halted at iteration 3 on the kl
guard (kl_mu 0.007 → 0.068, doubling per iteration), and six iteration-0 replays put it on the
optimizer — with the value and anchor gradients (2–5× the policy gradient) gone from the trunk,
AdamW's per-parameter scaling handed the trunk's whole step to the policy direction; the trunk at
lr/3.3 restored the control's kl_mu exactly (0.0020 vs 0.0024), the head lr alone changed nothing
on kl_mu and only the detached head's bias (v0 0.60 → 0.55).

**What rung 2 buys over rung 1′ (same seeds, same box time):** ≈ 1.1pp of the anchor's strength
cost back, the Spearman plateau 0.02 higher, and the anchor's cast → pass push gone (casts per game
28.9 vs 26.3; alloc 29.5). Open, routed to the launch ADR: whether the slower trunk lr is a strength
cost of its own over the big run's length (−0.47pp is inside noise; priced against alloc's kl_mu
track), and the 38% re-ask rescue rate (17–21% in every other cell) as a census read.

**Consequences for the steps that follow:** step 2 (the Ante re-measure) runs against
`settings-stopgrad-t3e6/iter-019`, the head of record for the leaf and the ledger; the shuffle
decision record (fork) proceeds as written. The drifted-trunk recovery read (a short continuation
from `shakedown-alloc/iter-019` under this recipe) decides the big run's warm start and is a
launch-ADR item. A standing rule is born (below); ADR-0118's audit-and-anchor rule stands with the
anchor now head-only.

