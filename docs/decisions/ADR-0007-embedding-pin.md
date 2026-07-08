# ADR-0007: Embedding pin — Qwen3 stays; ablation is a rung-1 tie

- **Date:** 2026-07-07
- **Status:** accepted
- **Design-doc anchor:** m1-bc-plan.md D5 ("Embedding ablation (Qwen3 vs BGE-M3) decides the pin"); §1 card encoder

## Context

Full-epoch A/B on the 50K pilot (113K steps, v3 conditioning — the fusion-
scale fix that made the text channel audible, ADR-less but see devlog
2026-07-06 session 5), 600-batch final eval (nonpass SE ~0.33%):

| metric | Qwen3-Embedding-4B (2560d) | BGE-M3 (1024d) |
|---|---|---|
| honest agreement | 0.9636 | 0.9630 |
| nonpass agreement | 0.8373 | 0.8350 |
| target-slot acc | 0.9654 | 0.9654 |
| value BCE | 0.5746 | 0.5744 |
| valpair honest / nonpass | 0.9656 / 0.8385 | 0.9651 / 0.8413 |

Statistical tie on every axis at a power that resolves ~1pp nonpass
differences.

Two caveats bound what this measures:
1. **In-pool only.** Train and eval share the same 1,701-card pool, so
   cross-card generalization — the axis where text embeddings should earn
   their keep (unseen cards, Tutor's pool search) — is structurally
   invisible to this ablation.
2. **Rung-1 only.** Source selection + rung-1 targets may simply not need
   rules text beyond what structured features + card identity + board
   dynamics carry; deeper CastPlan rungs and mid-resolution choices may
   differ.

## Decision

- **The pin stays Qwen3-Embedding-4B** (rev `5cf2132abc99`). Switching buys
  nothing measured; Qwen3's NN structure (clean mechanic clustering vs
  BGE's looser neighbors, D4 spot check) is the better prior for exactly
  the axes this eval could not measure.
- **BGE-M3 is a validated drop-in escape hatch** — full training run, no
  regression, config-flag swap. The m1-plan risk line "Qwen3 rules-text
  fit — the D5 ablation decides; escape hatch designed" resolves: no
  misfit; hatch tested and real.

## Consequences

- The D5 ablation deliverable is done; no embedding work blocks D7.
- Finding worth carrying forward: **rung-1 policy is text-insensitive
  in-pool** — structured features + ID + dynamics suffice. Re-test at the
  point where cross-card generalization first matters for real (held-out
  *cards*, not just held-out matchups — a Tutor-era eval), before assuming
  text embeddings are pulling weight anywhere.
- **Confirmed by direct removal (run8-textnull, same day):** zeroing the
  text buffer entirely costs −0.19pp honest (borderline ~2.8σ) and nothing
  measurable elsewhere (nonpass/target/X/value all within noise). The
  Qwen3-vs-BGE tie therefore reads "text barely used," NOT "both encoders
  equally good" — encoder-scale questions (e.g. Qwen3-8B) are closed for
  rung-1 in-pool. Corollary: shortcut learning is real here — with the ID
  channel available, the model does not build the text pathway. **ID
  dropout** (randomly blanking card identity in training) is the known
  lever to force the text pathway alive before any subsystem (Tutor,
  pool expansion) needs cold-start card evaluation.
- Cache economics are a non-factor either way (frozen fp16 buffers, ~9 MB
  vs ~3.5 MB; 0.8M param delta in the fusion layer).
