# ADR-0040: M6 D2-A labeling re-price — the labeler is engine-bound; micro-batching's "2–4×" falsified; drill mode is the cheap tranche path

- **Date:** 2026-08-06
- **Status:** accepted
- **Design-doc anchor:** §6 (Grindstone economics), §4 (rollout-label
  value targets)
- **Inputs:** [ADR-0039](ADR-0039-d1-frozen-probe-resolution.md) (the
  "between" verdict that made this the sanctioned next step),
  [ADR-0015](ADR-0015-d4-closeout.md) (the stale economics being
  retired), [ADR-0032](ADR-0032-d4-serving-path-resolution.md) (serve
  ceiling = waiting; w=16 + chunk-clamp recipe),
  `scripts/bench_labeler.py` (the instrument, built this session),
  `data/runs/labeler-bench.json` + `labelbench-w16-20260805-205330/`
  (the measurement), `data/runs/drill-map-r11i19-k8/` (the measured
  drill-mode comparison).

## Question

ADR-0015 priced rollout labeling at ~17 positions/h/worker (K=8,
turn-stratified) through a batch-1 server, projected "50K labels ≈ 15
days," and parked the machinery with "server micro-batching is the
mandatory first lever (2–4× plausible)." The serve stack has since
gained GPU micro-batching (D6) and the w=16 + ≥2-round chunk clamp
(ADR-0032). What does labeling cost today?

## Measurement

`bench_labeler.py`: smoke (8 games, K=4 — the parked `-points` mode's
first run since M2 D4, clean on the post-rebase jar) + the priced arm:
160 pool games, w=16, K=8, 4 turn-stratified points/game, argmax serve
of `iter-019` on the micro-batching server, `--reask`, census off
(standing labeler rule), chunk clamped to 5. Conditions: live desktop,
possible background Kopia upload (0% iowait, ~40% CPU idle observed) —
a pricing bench, not a calibrated read. Accounting deduped by (game,
fork point) — crash re-launches replay partial games and re-append
label rows (85/689 raw rows were duplicates; the script now dedupes).

## Result

**Fresh-mainline sampling labeler (the ADR-0015 mode): 604 unique
labels in 3.41h = 11.1 positions/h/worker (177/h fleet at w=16) —
0.65× ADR-0015's per-worker number.** Fleet-wide, w=16 still nets ~1.3×
the old ~139/h. "50K labels ≈ 15 days" retires to **≈ 11.8 days** —
better, but nothing like the parked projection.

**The "2–4× from micro-batching" hypothesis is falsified.** The server
log shows batching fully engaged (sizes 2–16, mass at 2–8); the GPU was
never the constraint at fleet scale — consistent with ADR-0032's serve
profile (0.05 ms Python-active vs ~5.3 ms wall; the ceiling is
waiting). The labeler's cost is **engine-side game-playing**: each
labeled game plays a full mainline plus K×points completions to game
end on the JVM (fork-block p50 124s, p90 223s, max 978s at K=8).
Per-worker regression vs 2026-07-13 is explained by the environment,
not a defect: iter-019 vs the BC-era policy, the post-rebase engine,
`-reask` on, and completions that run to the end of today's longer
games. 604/640 nominal points materialized (games that end before a
sampled target turn skip it); 156/160 mainlines decisive.

**The measured cheap path is drill mode:** `drill-map-r11i19-k8`
(2026-08-04) produced 565 K=8 labels in 2.59h at w=8 = **27.3
positions/h/worker (218/h fleet)** — ~2.5× the sampling labeler per
worker *despite* labeling deeper positions (fired turns ~21–28),
because exact replay ends at the fork turn and `-drillstop` never
completes the mainline. Loss-adjacent positions — exactly the
population the ADR-0039 learning curve lives in — are the *cheap*
ones.

**Crash tax, now with numbers:** 37/4,832 completions crashed (0.77%);
83 worker invocations vs 32 planned spans (~51 crash re-launches);
~12% of label rows were replayed duplicates (wasted work). One
long-tail game (134) burned a worker and produced 159s fork blocks.
The carried fork stability pass (IndexOOB, targeting-retry, MayPlay
`.get(0)`, MinMaxBlocker) stays the pre-campaign gate — at campaign
scale this tax is throughput.

## Consequences

1. **The ADR-0039 tranche is affordable and should be generated in
   drill mode**, not fresh-mainline sampling: expand loss-adjacent
   positions from the era stores (more anchor offsets per loss,
   sweep-style; more losses from the closing-read arms) and rollout at
   K=8. Measured price: 5K labels ≈ 23h fleet at w=8; ~11–12h at w=16
   if per-worker throughput holds (projection — w=16 drill mode is
   unmeasured). Order 5–10K/era ≈ 1–2 days of box time per era.
2. **Fresh-mainline sampling remains the price for distribution-matched
   campaign labels** (a future path-A distillation set): 177/h fleet,
   50K ≈ 11.8 days. Sized only after the path verdict — per ADR-0039
   the tranche and extended curve come first.
3. **ADR-0015's parking clause resolves:** "returns behind server
   micro-batching" — the return happened, but the lever that mattered
   was the drill machinery M4 built in the meantime, not the server.
   Efficiency posture unchanged: no further serve-side work for
   labeling (measured closed).
4. **Fork stability pass ordering unchanged** (pre-campaign gate,
   m6-plan D2-A.2), now justified by a measured 0.77% completion crash
   rate + ~12% re-launch waste rather than anecdote.
5. `bench_labeler.py` joins the standing bench tools (dedup-correct;
   ADR-0015 constants embedded for comparison).
