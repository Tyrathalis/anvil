# M12 plan — SEARCH AS THE BEHAVIOR POLICY (CHARTER DRAFT, 2026-09-06)

*Status: DRAFT at the M11 closeout ([ADR-0100](../decisions/ADR-0100-m11-closeout.md)). Forks
carry leans; the scoping session adjudicates. Principle the user set for the milestone: the
project can identify strength opportunities and cannot teach them — the next priority is the
teaching channel, and search depth must be an easy scaling lever from day one.*

## Charter

**The behavior policy that generates training data is the network PLUS a bounded lookahead
through the engine, evaluated by the network's own masked value head; the network is trained to
reproduce what the lookahead chose (distillation) and on what it earned (PG), at store scale.**
Search is the improvement operator applied at every searched window of every game, amortized by
the loop that already trains on millions of windows — not a label mint applied to one window in
twenty. The lookahead is one directive with three knobs — **depth d (plies of the acting seat's
decisions), breadth b (options expanded per ply), leaf rolls K** — so deeper search is a flag, not
a build. Deployment is the network alone; the gap between network-alone and with-lookahead reads
is the amortization measure and the deployment-lookahead price in one number.

## The facts it starts from (ADR-0098, ADR-0099, ADR-0100)

- One engine step plus the value head ranks option quality at 0.30 (one ply) and 0.46 (the
  spread's horizon, K=8) with no learning; the masked head — the only critic that may act
  (information-set principle) — is within 0.03 of the full-vis critic at every horizon.
- Nothing learns option quality from the pre-action state at 10³ labels (0.20 at best; a length
  prior explains most of it); the slope says 16× data for a number the critic gives for free.
- The loop's existing amortizers are exactly the ones this needs: the grounded label term
  (ADR-0088: subsampled chunks, warmup, carry-w, memorization tripline) for distillation of
  searched picks, PG/V-trace on realized outcomes, the paired strength read (SE 0.7pp at K=8/N=600)
  as the day-zero and mid-run instrument, `-forceschedule`-class directives + GameCopier +
  `Obs.peekPriority` as the copy/apply/snapshot machinery, the void-arm finding (illegal-at-apply
  options are detected at copy time — the pre-filter comes free).
- The value head's STATE ranking is itself weak (Spearman 0.27–0.48 vs rollout truth, M5/M6):
  lookahead can only be as good as the leaf value, so sharpening the head is a build, not a hope.
- Luck correction of returns is worth ~5% until the critic improves (ADR-0014/0015): not a lever
  now; it rides behind value-head quality.

## The canonical shape

1. **The search directive** (`-lookahead`, Java; inert without the flag): at a searched window of a
   bridged seat with presented options O, for each o ∈ O (breadth b: all, or the policy's top-b by
   logit): copy the game (GameCopier, CRN roll seed), apply o, advance with the EXECUTOR playing
   every intermediate decision (both seats) to the **leaf event** — for d=1 the acting seat's next
   quiescent priority window (or game end); for d>1 recurse b-wide from that window for d plies;
   snapshot the leaf as a peek record; ask the bridge `anvil.value` for V(leaf) from the acting
   seat's masked value head; K>1 = leaf rolls under reshuffle. Illegal-at-apply options are void
   (score −∞), counted. Returns per-option leaf values to the mainline. Cost ≈ Σ over expanded
   nodes of (copy + apply + run-to-leaf); d=1, b=all, K=1 ≈ |O| copies of a fraction of a turn.
2. **The acting rule** (the behavior policy): the executor's own pick is scored like every other
   option (its leaf value = the natural line); margin = max V − V(natural). **Margin ≥ bar → act on
   the search's pick** (sampled from softmax over leaf values at a temperature, so a behavior
   distribution exists for PG and exploration survives); below the bar → the executor's pick as
   today. The natural line is never worse than the executor by construction. Full-vis NEVER acts
   (§7): the search's leaf value is the masked head, so the behavior policy sees only its
   information set.
3. **The gate as the compute lever** (with d, b, K): Build 0 searches every eligible window and
   MEASURES; from Build 2 the state-level pivotality predictor (AUC 0.69, a forward pass) decides
   which windows get searched at what (d, b, K) — the flywheel's seed, finally used as a read-out
   that aims compute rather than labels.
4. **Amortization** (two terms, both existing): a **distillation term** on the searched windows —
   the policy logits toward the search's pick (the ADR-0088 grounded-driver machinery, dense: every
   searched window is a label) — and **PG** on every window with the behavior logp (the search's
   softmax where it acted, the executor's otherwise; V-trace corrects the rest). Trainable trunk,
   one network, as today.
5. **The value head** (Build 1): a rank loss for the masked head on targets the engine already
   banked — the full-vis critic's h2 values and the K-roll rollout means (ADR-0015: rollout means
   out-rank the critic as outcome predictors) — read by the Build 0 cells (one-ply ranking vs the
   spread: 0.28 today) and the state-ranking Spearman (0.27–0.48 today). Every downstream read
   moves with this number.
6. **Surfaces = search TAGS.** Priority windows first (the funded ceiling lives there). Payment
   classes are the cheapest lookahead (apply a class, resolve, evaluate) and return as a tag in
   Build 2, read by the payment holdout; every other tag (targets, triggers, combat) waits on the
   same directive with its own leaf event.
7. **Deployment.** The network alone on a phone; where compute exists, the same directive
   server-side at whatever (d, b, K) the gap read prices. Amortization is measured, not assumed.

## Forks (leans in bold; adjudicated at the scoping session)

- **A. Leaf event for d=1.** **The acting seat's next quiescent priority window** (cheap, generic
  across tags, the state the executor would actually face next) vs end of the acting turn (the
  Build 0 cell, 0.30, but a turn of play per option). The two-ply case (d=2) reaches end-of-turn
  naturally when the next window is the same turn's.
- **B. Amortization term.** **Distillation (dense label term) + PG** vs PG alone with forced-row
  logp (the ADR-0094 machinery). Distillation is the AlphaZero-shaped target and the machinery is
  proven; PG alone would rely on the search's picks earning more, which is what the day-zero read
  must first show.
- **C. Behavior at searched windows.** **Sampled from the leaf-value softmax (temperature pinned
  pre-data)** vs argmax. Argmax kills exploration and the PG behavior distribution.
- **D. Gate.** **Build 0 searches every eligible window** (measure the cost and the margin
  distribution first); the pivotality gate + the margin bar are pinned from Build 0's data.
- **E. Reads.** **The paired strength read on the fixed population** (SE 0.7pp) is the day-zero
  and mid-run instrument: with-lookahead vs the executor at Build 0 (the ADR-0095 rule — a regime
  that replaces the executor's pick is gated by a day-zero read against it), network-alone vs the
  ckpt of record mid-run, and both at close; **the standard 2,000-game read closes** (network
  alone = the promotable number; with-lookahead = the deployment-lookahead ceiling).
- **F. Depth as the lever.** d=1 at Build 0; **d=2 and K>1 read as a scaling curve at Build 3** at
  matched compute per game (the gate rate trades against depth). Breadth b caps the branching at
  the policy's top-b for d ≥ 2.

## Build order

0. **The directive + the day-zero read (R3).** Java `-lookahead d b K` + the void-at-apply
   pre-filter; server `anvil.value` (masked head, batched); the acting rule with a margin bar and
   softmax temperature; smoke (determinism under CRN, cost per searched window); **the day-zero
   paired read: with-lookahead (d=1, all windows, K=1) vs the executor on the fixed population.**
   PRE-REGISTER: **≥ +1.5pp GO** (the search improves play at day zero — amortize it); **≤ 0
   KILL-CANDIDATE** (the value head cannot rank options well enough to act on; Build 1 first, then
   re-read once; a second ≤ 0 kills the charter); between → Build 1 then re-read.
1. **Value-head sharpening.** Rank loss on banked full-vis h2 values + rollout means for the
   masked head; reads = the Build 0 cells (one-ply ranking 0.28 →) and the state-ranking Spearman;
   the day-zero read re-run with the sharper head. KILL: no movement on either cell.
2. **The amortization run.** Generation with lookahead as the behavior policy (gate + bar pinned
   from Build 0's distributions), distillation + PG, one network; paired reads at day zero,
   mid-point, terminal for BOTH network-alone and with-lookahead; the payment tag joins here.
   KILL: network-alone flat at mid-point while with-lookahead is up (nothing amortizes).
3. **The depth lever.** d=2 / K=2 / gated variants at matched compute: the scaling curve on the
   paired read. This is the "easy scaling lever" the charter promises, measured.
4. **Close by the standard 2,000-game read** vs 0.5279 ± 0.0110 (network alone; promote on
   cleared gate), with the with-lookahead read alongside as the deployment ceiling.

## Done-when

1. The directive runs at d ∈ {1, 2} with b and K as flags; cost per searched window measured; the
   day-zero paired read recorded and adjudicated on its bars.
2. The value head's one-ply ranking and state ranking move under Build 1 (numbers pre-registered
   at the scoping session against the Build 0 cells).
3. One amortization run with paired reads at day zero / mid-point / terminal for network-alone
   AND with-lookahead; the gap read recorded.
4. The depth curve (d=1 vs d=2 at matched compute) recorded.
5. Closed by the standard 2,000-game read — or early by a pre-registered kill with an ADR.
6. The closeout routes the queue by name (stack-entry tokens, semantic option content, tutor
   targets, trigger order / combat damage, §3b stops, mull tuck).

## Inherited obligations and hazards

- **Information-set principle:** the behavior search evaluates leaves with the MASKED head only;
  full-vis stays instrument-only (§7). Leaves are the acting seat's own future windows, so the
  search never reveals hidden information to the policy.
- **Engine change = boundary unless ADR-0025-proven:** `-lookahead` is inert without the flag;
  the flag-off jar identity is proven by forkcheck before the first generation store; with the
  flag on the game path changes BY DESIGN (that is the policy, not the engine) — stores carry the
  directive's (d, b, K, gate, bar, temperature) as provenance.
- **Serving jitter** bounds replay parity; reads pair within-run (CRN).
- **Reads that measure ceilings are not learnability** (the ADR-0100 rule): the day-zero read
  measures acting strength directly; amortization is read as the network-alone gap, never
  inferred from label fit.
- **Compute accounting per game** (searched windows × nodes × leaf evals) is a first-class
  telemetry row from Build 0 — the scaling lever is only easy if its price is always visible.

## Out of scope / routed by name

The certifier and spread labels (read instruments only); the option scorer's spread loss
(retired, ADR-0099); tree search on device; tutor targets, trigger order / combat damage, §3b
stops, mull tuck (re-ranked at the scoping session); stack-entry tokens and semantic option
content (M12's representation completions, funded after Build 2 moves strength).
