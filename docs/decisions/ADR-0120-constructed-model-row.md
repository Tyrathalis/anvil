# ADR-0120: The Constructed model row — a format column that inserts at the one-hot's end, with one layout map for every checkpoint and bank

- **Date:** 2026-09-27
- **Status:** accepted (the post-run worktree after the shakedown; the identity tests in `tests/test_format_row.py`)
- **Design-doc anchor:** §1 (encoder, the game-agnostic schema), §2 ("format as features", ADR-0111); [format-onboarding.md](../design/format-onboarding.md) "Adding a format" (this ADR is its worked example, landed); ADR-0018 (dataset-boundary chunking)

## Context

The quickstart's headline path for outside readers is Constructed (60-card lists in the `pauper`
slot), and since the M9 format one-hot (2026-08-21) every Constructed game raised `VocabError` at
featurization: `vocab_mtg.json` listed only `Commander`. Found at the 09-23 documentation pass,
routed to this worktree.

Adding the row is one vocab entry and one column, but the column's POSITION is the trap the
onboarding doc named: since Build 4 the five format scalars follow the one-hot, so a new one-hot
column lands mid-globals. The checkpoint loader (`load_compat`) padded new global columns at the
globals' END — right for the scalars, wrong for a one-hot column: every older checkpoint would
have read its scalar weights through the new column and the new column's zero through the first
scalar's weights. The pre-featurized Build 1 banks (`widen_globals`, the state-ranking eval and
now the value anchor) had the same append-only assumption.

## Decision

1. **The row.** `Constructed` (Forge `GameType.Constructed`) appended to the vocab's `formats`
   with its scalars (20 life, 60 cards, no singleton, no command zone, London mulligan) and
   `fmt_constructed` after `fmt_commander` in `GLOBAL_FEATURES`; `GLOBAL_SCALE` grows with it.
2. **One layout map.** `transform.globals_layout(width)` reads any globals width the encoder ever
   produced as (base, one-hot count, scalars present) — the base columns, then the one-hot (one
   column per known format, appended per format), then the scalars, which arrived after at least
   one one-hot column existed, so a width past base + scalars carries them; every other width is
   loud. `widen_globals_columns(width)` is the insert map: saved one-hot columns keep their index,
   saved scalars move past the newer one-hots. **Both consumers use it:** `model.pad_state_proj`
   (the checkpoint loader; a CPU-loaded state onto a CUDA net) and `value_pretrain.widen_globals`
   (the banks). A format addition is therefore one vocab row + one feature column; nothing else
   moves.
3. **The proof is the identity test**, not an argument: a saved projection re-laid onto today's
   columns projects a saved-layout input, mapped through the same column map, to the same output,
   for the M1–M8, M9 and Build 4 widths; the new column's weights are zero; a Constructed header
   featurizes to its own row and a Commander header to the same base columns as before.
4. **Checkpoints record their layout** (`config["global_features"]`, the BC and RL savers) so the
   next such change can refuse a mismatch instead of inferring from widths.

## Consequences

- **Not a numeric boundary for Commander reads.** Every Commander game featurizes to the same
  columns plus one zero; every older checkpoint serves byte-identically through the pad; a warm
  start trains the new column's weights at zero input (zero gradient). The shakedown's numbers and
  `iter-019` stay comparable across this commit. The dataset-boundary event ADR-0018 names is the
  **first Constructed data** in a training mixture, not the row — that ADR is written when a
  Constructed run is scoped (the onboarding checklist's step 4 smoke first).
- The quickstart's Constructed column is live again; the "blocked on current main" notice goes.
- Standing rule (engine/data hygiene): a format addition edits the vocab row and the feature
  column and nothing else; every pre-featurized asset and checkpoint reads through
  `globals_layout`, and the change lands with the identity test green.
- Routed: the step-4 smoke (a two-deck Constructed pool, 20 heuristic games with `--obs`, ingest,
  1,000 BC steps) at the next quickstart pass — the row is proven at the encoder and the loader,
  not yet on a played Constructed game.
