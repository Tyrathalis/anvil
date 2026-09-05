# ADR-0097: M11 charter ADJUDICATED — the option scorer is the policy's action head (single network, advantage semantics); payment classes are the second surface; the one-surface rule becomes one MECHANISM per milestone; the standard read closes

- **Date:** 2026-09-05
- **Status:** accepted (user adjudication at the M11 scoping session, the same day the
  charter was drafted at the M10 closeout)
- **Design-doc anchor:** [m11-plan.md](../design/m11-plan.md) (doc of record, forks A–F);
  anvil-design-v2 §3 (pointer decoder), §3a (pivotal-turn search + expert-iteration
  distillation), §3c (payment classes), §3d′ (the coverage ledger and its standing rule),
  §6 (Grindstone's ε-pivotality mining, search distillation); ADR-0096 (the facts)

## Context

Four milestones tied or halted at the strength gate. ADR-0096 named the root: the
search's improvements are real (+13.5pp under an oracle, label reliability 0.66) but
sparse, state-specific, and invisible to the executor's frozen representation, while
PIVOTALITY — "does this window have an option worth taking" — is learnable from the
same representation (AUC 0.69, rising). The M11 draft chartered an OPTION SCORER over
that finding and left six forks with leans. The user asked that this milestone make the
design more canonical, elegant and complete, so that capability work (surfaces, then
cards and modes) can resume on a mechanism that amortizes rather than on one bespoke
head per surface.

The observation the adjudication rests on: the model already has exactly one scoring
operation. The priority pointer head, the payment goal options (M9 rung 3, "no new head,
the pointer path scores goal options") and the D5 combat row heads all compute
query·key over presented candidates; they differ in wrappers and in training semantics
(BC/PG log-probs on the realized pick). That seam is what the scorer closes.

## Decision

**The charter statement:** every decision the engine presents is a list of options; the
network scores each option as an advantage over the natural line; one label format (a
per-option Δ spread on the store row, produced by the certifier at any decision tag)
feeds that score at every surface.

Four adjudications:

1. **Fork B — SINGLE NETWORK.** The scorer IS the policy's action head with advantage
   semantics: score(state, option) = predicted Δ vs the natural line; acting = softmax
   over scores (temperature as today); the margin (top − natural) gates composite
   plan-type options and is the pivotality read-out everywhere; PG on realized outcomes
   trains every window and spread regression/ranking trains the certified ones, on the
   same logits, one trunk. The two-network form (frozen executor acting below the bar, a
   separate scorer with its own trunk gating it) is recorded and rejected: two trunks at
   serve, and the scorer's trunk would train on the sparse spreads alone. Build 1's read
   (a scorer fitted on a trainable copy of the trunk, Spearman vs the search's ranking)
   is identical under both forms; the executor-strength guard when the scorer takes over
   acting is the paired read at day zero (the ADR-0095 rule: a regime that replaces the
   executor is gated by a day-zero read against it).
2. **Fork A/F — PAYMENT CLASSES are the second surface of the same head**, not a parallel
   track and not their own head. Payment classes are already positional options on the
   pointer path; the ADR-0075 supervised conditional labels are per-option Δ spreads by
   construction (`payment_certify.py`'s 2-turn proxy); the surface's ceiling is measured
   (+2.96pp/game). It is the likeliest strength number to move and the test of the
   amortization claim (a surface costs a tag + a harvest) on a surface whose certifier
   already exists. Tutor targets, stack-entry tokens, trigger order / combat damage stay
   OUT, routed by name below.
3. **The §3d′ standing rule is AMENDED:** "one decision surface per milestone" becomes
   **"one decision MECHANISM per milestone; surfaces attribute through per-tag reads"** —
   per-tag spreads from the certifier and the paired read with the mask closed per tag.
   The original rule (the M9 lesson: attribution dies at two) still binds any surface that
   lacks its own per-tag read.
4. **Fork E — the STANDARD 2,000-game combined paired read closes the milestone**
   (`scripts/final_read.py` vs the post-boundary baseline 0.5279 ± 0.0110, promote on
   cleared gate). The fixed-population paired read (SE 0.7pp) is the mechanism and mid-run
   instrument, never the closer (it reads a selected population).

Forks C (label target: h2 composite spread; critic lookahead read first) and D
(certification weighting: 30% uniform floor + pivotality) keep their leans; C is
adjudicated by Build 0's read, D is pinned at Build 2's launch.

**Named consequence of the charter, recorded so it is not rediscovered:** under the
scorer, the ceiling measurement and the label harvest are the SAME run — the certifier by
tag produces per-option spreads, and rate × best-option Δ is the gate-scale ceiling. The
measure-the-ceiling rule (ADR-0073) is satisfied as a side effect of harvesting labels at
a new tag. And Grindstone's mining criterion (§6, ε-pivotality: the decision flips the
rollout outcome) IS the scorer's spread; drill selection, certification aiming and the
deployment lookahead gate become one read-out.

**Critic lookahead's two critics (named for Fork C):** the training-time labeler uses the
full-visibility critic (the ADR-0015 asymmetric critic, instrument-only by §7); any
deployment-time lookahead can only use the policy's own masked value head, whose
reliability against rollout spreads is a SEPARATE read, not implied by Build 0's.

## Routing by name (no-silent-loss)

- **Tutor/fetch targets** — the third surface candidate; re-ranked at the NEXT scoping
  session against ADR-0080's 1.41pp/g pricing, once payment has measured the per-surface
  cost of the scorer. Not silently absorbed by the multi-surface charter.
- **Stack-entry tokens (§J item 10)** — a representation completion (obs already carries
  `obs["stack"]`; encoder-only, no boundary event). Neither M11 surface needs it; the
  first mid-resolution or trigger-response surface funds it, and it must land BEFORE that
  surface's harvest (a blind scorer at a trigger window learns the wrong thing).
- **Trigger ordering / combat damage assignment** — SELECT-shape surfaces the scorer
  would amortize; ceilings unmeasured; under this charter the certifier by tag measures
  and labels them in one run when their tag is bridged. Next scoping session.
- **§3b learnable stops** — unchanged: an episode-economics lever, ranked behind strength.
- **Mulligan tuck at serve (§J item 5)** — a free completion (`TAG_TUCK` Java-side, loader
  trains `mull_tuck`, server's `TAG_TASK` does not advertise it); folds into the first
  session that touches `TAG_TASK`, not a milestone item.
- **Cost-composition cousins / costmod / pool-tie** — CLOSED at ADR-0083 (landed
  2026-08-28); leaves the queue.
- **Deployment lookahead on the masked value head** — named above; funded by the gap
  between the network-alone read and the server-side lookahead read at M11's close.

## Consequences

- m11-plan.md is the doc of record with the forks marked adjudicated; its build order
  gains the payment surface at Build 2 and a done-when list.
- Design doc §3d′'s standing rule is amended in place with a pointer here;
  standing-rules.md carries the amended rule under Scoping and routing.
- The executor's cast head is not frozen: the scorer's training touches the acting logits
  from Build 3 on, so the ADR-0085/0087/0088 grounded-driver machinery (subsampled label
  chunks, warmup ramp, carry-w, memorization tripline, share guards) is the label-term
  driver from birth, and the paired read at day zero is the guard.
- Pricing: every rolled-out window yields a spread (not only the ~20% certified), so a
  mint-scale pool of ~2,700 spreads is ~8 harvest batches ≈ 20 h at 8 workers (two
  overnights), before the void-arm pre-filter and pivotality aiming raise the yield.
- Products: the scorer's margin is Mentor's per-decision "how much this choice matters"
  and Tutor's dense per-card realized advantage (§5) — downstream, not chartered.
