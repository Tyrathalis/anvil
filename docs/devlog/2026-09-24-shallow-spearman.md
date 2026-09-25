# 2026-09-24 (evening) — shakedown status; the shallow arm's early Spearman

## Done

- Status read on `shakedown`: alloc closed 14:27 at 0.5405 ± 0.0111; shallow launched 14:27, in
  iteration 5 at 20:10, ≈ 53 min per iteration (half alloc's cadence → ≈ 32 iterations expected),
  GPU 71%, disk 44%, no kl-abort / tripwire / NaN; battery flags only the kl_mu-growth note and 1–3
  fallbacks per iteration. Iteration-4 paired read 0.480 / 0.515 (± 2.5pp), one noisy early read.
- State-ranking Spearman on shallow iterations 0–4 (`value_pretrain eval`, CPU, niced) and the
  missing alloc 1–3 + recipe 3 rows, appended to `data/runs/shakedown/state_ranking.jsonl`. Finding
  in the running record: the shared iteration-0 step is there; the iteration-4 drop is not (yet).

## Broke / surprised me

- The iteration-4 network-alone arm read counted five `BridgePoisonedException` games: all deadline
  on `mtg.priority` seq=14 within turns 1–2, 25 s into each worker — the model server's cold start
  against the 20 s bridge deadline. Recycled, not replayed. Alloc's iteration-9 read had one.
  Routed post-run: a warm-up ping before the harness launches its workers.
- Shallow's iteration wall is ≈ 55% of alloc's; iteration-indexed comparisons across arms are not
  box-time comparisons — state both.

## Next session picks up

- Shallow Spearman at iterations 8 and 12 (25 s each; ~1 min total) — does it hold or drop late?
- Shallow closes ≈ 09-25 21:00–22:00; deep launches from the chain; verdict ≈ 09-27.
