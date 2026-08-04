# ADR-0032: D4 serving-path throughput — the lever was generation shape, not the serve path

Date: 2026-08-03
Status: accepted
Context: M4 D4 (promoted infrastructure deliverable), the 2026-08-03
bench retraction, mini-run `d4-w16val`.

## Result

**Done-when #4 — serving path profiled + measured improvement — is
SATISFIED.** The measured lever is generation *shape* (worker count +
per-batch chunk sizing), not serve-path code: an end-to-end mini-run at
the new configuration generates **~+30% faster in-loop** than the run11
reference, with the training pipeline (ingest, μ join, critic, V-trace,
tripwires, guards) unchanged and clean.

| config | in-loop gen throughput (gen_s basis: generation + ingest) |
|---|---|
| d6-run11, w=8 / flat chunk 30 (20 iters) | median 1025 g/h, range 862–1219 |
| `d4-w16val`, w=16 / per-batch clamp (3 iters) | 1589 / 1183 / 1291 g/h, mean ~1354 |

Every mini-run iteration beat run11's median; two of three beat its
20-iteration maximum. Median-vs-median the lever reads **+26%**,
mean-vs-median **+32%** — far outside run11's own iteration-to-iteration
spread. At run scale that is ~28 min/iteration → ~22, or roughly 2
hours returned per 20-iteration run.

## The profile verdict (what D4 was originally hunting)

The serve-path profile (v3, 28,000 requests / 50,750 census decision
events) measured **0.05 ms Python-active per request** against ~5.3 ms
wall at saturation: the serving ceiling is ~100× dominated by waiting
(micro-batch window, gRPC round-trips, scheduler wakeups), not by any
Python we could optimize. The originally-envisioned levers
(featurization caching, tensor assembly, proto handling) are therefore
dead ends at two orders of magnitude below the noise floor — the
documented negative D4's bounded-deliverable rule anticipated.

What the noise-floor discipline found instead (full story: 2026-08-03
devlog) was the **chunk-tail artifact**: a generation batch that
resolves to fewer than two chunks per worker is paced by its slowest
worker's contiguous deck-pair block (an 11× finish-time spread observed
in the wild). This first produced a false "37% environment regression"
(retracted same day), then overturned the standing "w=16 is 6% slower"
conclusion — and the §6d batch split made it a *live defect in the
training loop*: at 480 games with `heur_frac 0.5`, generation is three
separate launches (mirror 240 + heur 120 + 120), so run11's flat
chunk 30 gave the mirror batch exactly one round and left half the
heur-batch workers idle.

## Decision

1. **Driver hardening (landed `7e34eab`):** `batch_chunk()` clamps
   `args.chunk` per generation batch to guarantee ≥2 rounds per worker
   (`args.chunk` stays the ceiling; mirror 240@w16 → 7, heur 120@w16 →
   3). Same rule as the `bench_generation.py` hardening. Throughput-
   only: game seeds, provenance, and store semantics are untouched.
2. **The standing recipe adopts `--workers 16`** (chunk ceiling 30
   unchanged, clamp does per-batch sizing). Validated end-to-end in
   `d4-w16val`: 3 iterations of the run11 recipe verbatim (init +
   critic + mainline = `d6-run11/iter-019`, fresh seeds 20260803, no
   drills — selection stale per ADR-0031, arms off), zero guard trips,
   zero anomaly flags beyond the routine `fallbacks` class, chunk-3 JVM
   recycle overhead measured harmless (heur batches sustained
   ~1400 g/h).
3. **D4 is CLOSED** on clause "measured improvement" + the attributed
   negative for serve-path code. No further serving-path work is
   scheduled; the micro-batch-window / UDS / affinity lever ranking
   stays on file in the devlog if generation cost ever re-dominates.

## Consequences

- All four M4 done-when clauses are now satisfied (#1 ADR-0028, #2
  D2.4, #3 ADR-0031, #4 this ADR). **M4 closure is put to the user** —
  the remaining queued-but-unscoped items (mid-run decomposition phase
  shipped 2026-08-02; drill curation regen from iter-019 losses) are
  next-run work, not open deliverables.
- Cross-era throughput comparisons are valid only at identical
  chunking (standing lesson from the retraction). run11-era gen_s
  numbers are the last of the flat-chunk shape; future in-loop
  comparisons baseline on `d4-w16val`'s configuration.
- `d4-w16val`'s checkpoints are scratch (3 guarded iterations off the
  ckpt of record, kept only as the lever's evidence run) — nothing in
  it is promotable and its stores stay out of future replay mixtures.
- The mini-run's iter-000 banked one more seed-pinned repro pair for
  the carried engine-crash classes (NPE + IndexOutOfBounds; crash rows
  in `data/runs/d4-w16val-i000-20260803-202558/games.jsonl`).
