# ADR-0027: M4 opening sequence — Grindstone spine, new-engine grounding first, throughput promoted

- **Date:** 2026-07-28
- **Status:** accepted
- **Design-doc anchor:** §6 (Grindstone), §7 (Ante); seeds the M4 plan doc
  per the M1/M2/M3 pattern
- **Inputs:** [ADR-0026](ADR-0026-m3-closeout.md) (closeout + standing
  agenda), [ADR-0024](ADR-0024-run8-batch-lever.md) (the absent-signal
  diagnosis), [ADR-0025](ADR-0025-d4-rebase-closeout.md) (re-baseline, the
  unresolved mechanism question), `data/runs/early-doom-run7b-i14/` (the
  531-loss curation list, old-scale), [m3-candidates.md](../design/m3-candidates.md)
  (leftover menu).

## Context

M3 closed with the recipe family at its measured ceiling and a specific
diagnosis: the near-tie residual is **absent signal, not gradient noise**
(ADR-0024 — variance halving trained equally then drifted; averaging more
zeros is still zero). The measured headroom is large (early-doom ceiling
0.83–0.92 vs ~0.55 — old scale) and NOT luck-bound. Whatever M4 is, its
spine must be a different signal source. Meanwhile the rebase moved the
scoreboard (RL ckpt 0.5530→0.5121 corrected, parity with the now-stronger
heuristic) and left a mechanism question ADR-0025 deliberately did not
chase: heuristic-got-stronger vs opponent-specific-fit loss.

Three structural facts shaped the sequencing:

1. **The curation list is old-scale in a deeper sense than its numbers.**
   Drill positions are reconstructed by replaying the game seed and forking
   at the crash window; old seeds produce different games on the rebased
   engine, so the 531-loss list is only replayable on
   `pre-rebase-20260725` — which fork discipline forbids training against.
   The curation analysis must be regenerated from new-engine games. The old
   list's standing value is that it validated the method and the tooling
   (`early_doom.py` reruns cheaply).
2. **Grindstone v0 is mostly machinery we already own.** The parked D4
   rollout apparatus (fork `-rollout K -points M`) already forks live model
   games at chosen windows and plays K re-randomized completions; twin
   determinism under the model (40/40) makes seed-replay-to-window sound.
   v0 ≈ re-aiming that machinery from *sampled quiescent* windows to
   *curated crash* windows. Its 17 positions/h/worker price was measured at
   batch-1, pre-micro-batching — it needs a re-price and will likely fall
   hard.
3. **No training signal has ever touched the new engine.** Every late-M3
   run (run-8 included) generated on the pre-rebase fork; the post-rebase
   work was four static reads. The two −4pp mechanisms are
   indistinguishable by any read (the diff-in-diff was underpowered) but
   diverge sharply under *training*: opponent-fit loss is recoverable in a
   few iterations of the standing recipe against the new opponent; a
   genuinely stronger heuristic is not.

There is also a clean theoretical alignment worth recording: K rollouts
from the same forked position give the crash decision an advantage
estimated from K outcomes instead of 1 — variance collapse *exactly at the
windows ADR-0024 flagged as signal-free*. Drills are not just extra data;
they are the direct mechanical answer to the diagnosis.

## Decisions (user, 2026-07-28)

1. **Identity: split milestone, Grindstone/signal spine dominant** — the
   M3 pattern. Upstream stays a watch-paced parallel track (the #11285
   nudge via the queued #11360 complementarity comment; the
   Copier→Snapshot consolidation only if maintainers engage).
2. **M4 opens with a new-engine adaptation probe, not a decomposition
   read** (run approved for the night of 2026-07-28). Continue the standing
   recipe (§6d mix + §6c penalty + §6f critic @ lr 1e-5, run-7b config
   verbatim) from `run7b/iter-014/{train,critic}` on the rebased fork for
   ~10 guarded iterations, fresh seeds. Interpretation is pre-registered:
   recovery toward ~0.55 ⇒ the drop was opponent-specific fit and the
   *adapted* checkpoint becomes the honest M4 baseline; flat ⇒ the
   heuristic genuinely got stronger and 0.5121 stands. Either way the probe
   produces the first new-engine self-play stores and (via its closing
   read) the substrate D2's curation regeneration needs. This is the
   resolution of ADR-0026's "re-baseline mechanism question": resolve it
   with a cheap run whose byproducts are needed anyway, not a bespoke read.
3. **Signal source (a) first: drill-mixed generation.** Position-
   initialized drill games mixed into the V-trace iteration store at a
   controlled fraction — the learner does not change. Escalation path
   documented but not entered up front: (b) K-rollout advantage baselines
   at pivotal windows, (c) per-candidate-action rollouts → contrastive/AWR
   labels (design §6 expert iteration, gated behind critic calibration +
   the anchoring trickle per the design doc). No skipping ahead.
4. **Grindstone v0 scope cut: the LLM filter and ddmin/wildcarding stay
   out** (§6 stages 3–4). They address drill generalization and
   minimization; v0's question is whether position-initialized signal moves
   winrate at all. Provenance tracing stays (invariant). Semantic
   minimization waits for a pass that has demonstrated signal.
5. **Serving-path throughput is a promoted deliverable, not a rider**
   (user: mix infrastructure into the milestone rather than grind
   inefficiently). Generation is ~80% of run cost post-collate and w=8
   already saturates the server's ~189 rps ceiling (~5.3 ms/request for a
   42M model — per-request Python overhead suspected). Protocol: noise
   floor first, then profile, then one measured lever. A 2× here multiplies
   every run in the milestone.
6. **Track C expressiveness stays deferred** (mode heads, AR combat
   decoder, pool breadth) — nothing in the loss forensics indicts
   expressiveness as the binding constraint. Re-entry criterion unchanged:
   a run has to demonstrate the need.

## Consequences

- First artifact: [m4-plan.md](../design/m4-plan.md) (same session).
- First run: `d6-run9` (adaptation probe) launches tonight on fork
  `master` @ `5fbc2ac98d`; ADR-0026's rule holds — no pre-rebase stores
  ever mix into M4 training.
- The early-doom/curation tooling reruns on the probe's closing read using
  the probe's own critic (trained on new-engine games by then) — fresher
  than the old-engine critic of record for trace generation.
- The falsified-lever ledger carries: temperature, batch size, and
  feature-alone are closed on this recipe family; M4 does not re-probe them
  except as explicitly post-rebase re-probes with a stated reason.
- Ante correctness items (draw-poison coverage, re-deal re-anchoring,
  node-level draw bias) ride only where a critic retrain touches them.
