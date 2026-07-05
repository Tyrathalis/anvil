# ADR-0005: D3 label mask = timing-legal candidates (payability unfiltered)

- **Date:** 2026-07-04
- **Status:** accepted
- **Design-doc anchor:** §3 (policy head action masking), §6 phase 1 (BC gate metric); amends [ADR-0004](ADR-0004-m1-scope.md) decision 4's "engine-legal options" wording and [observation-schema-v1.md](../design/observation-schema-v1.md) (amended in place, decision 5a + D3 amendment)

## Context

D2's priority-option scan logged "engine-legal, payable" options (`canPlay()` + `canPayCost` per SA variant). D3's 320-game validation batch (the first at that scale) surfaced two systematic corpus-poisoning classes totaling 74 errors:

1. **63 label hosts not in their own observation** — casts off the library top (Mystic Forge, Oracle of Mul Daya, Courser of Kruphix). `getAvailableCards` always includes every library top; the observation schema deliberately never serialized libraries.
2. **11 expert picks missing from the logged mask** — `canPayCost` over the raw SA disagrees with the AI's own pricing whenever costs depend on targets/X/additional costs (Mystical Dispute's conditional reduction, Dargo's sacrifice reduction, X spells, some commander casts). The engine's own comment in `AiController.canPlayAndPayForFace` states payability "can only be checked late," after `canPlaySa` sets targets and X.

The archaeology also killed the planned mitigation for the +77% w=16 obs haircut ("share the AI's scan"): **the AI never materializes an availability set** — `chooseSpellAbilityToPlayFromList` sorts by heuristic value and returns at the first `WillPlay`. There is nothing to share, and computing *correct* payability per window would require running the AI's heaviest step (target setup) per candidate.

## Decision

1. **The logged option mask is timing-legal candidates**: `canPlay()`-only (the same predicate the AI itself requires — `Spell.canPlay() == canPlayFromHost() != null`), plus land drops. The set is a **superset of the expert's castable actions by construction**; the expert-action-outside-mask failure mode is structurally impossible. Affordability is the model's to learn (it must price costs anyway to emit CastPlans); the D8 executor's veto path already covers model proposals that are timing-legal but unaffordable. `-Danvil.scan.paycheck=on` restores the old filter for comparison runs only.
2. **The gate metric's single-legal-option exclusion is defined on this candidate basis** (marginally stricter: fewer windows excluded than under a payable-only mask). §15's high-80s row resolves against this definition.
3. **Library tops are serialized under engine look permission** (schema decision 5a): `mayPlayerLook` drives presence and `vis` (`"all"` for Courser-class public reveals, `"c"` for Mystic Forge-class controller knowledge — matching the card scripts' `MayLookAt$` grants); priority decs additionally union any unwalked-zone option host into the snapshot, so a label's host is in its own observation by construction. Deeper library knowledge (scry-to-top order) remains the named v2 gap.
4. **Stale target refs are filtered at serialization**: a modal spell's sub-chain can retain `TargetChoices` from an earlier AI evaluation pass (observed once in 320 games: a dead token). Card refs are dropped unless currently in their zone; stack-SA refs unless actually on the stack. Resolution re-binds targets, so stale refs are evaluation noise.

## Consequences

- **Validation: 74 → 2 → 0 errors** across three 320-game batches (fork `57c094bc55` fixed classes 1–2; `ca76c842a8` the stale-ref residual). Zero-error validation is the standing pilot/corpus launch gate.
- **The w=16 obs haircut collapsed from +77% to +18%** (923 s obs-off / 1,638 s old scan / 1,092 s new scan per 320 games; 1,248 → 703 → 1,055 g/h) — dropping mana enumeration from the scan was the lever, delivered by the correctness fix for free. Scan-sharing as a concept is retired. Ref-dedup stays un-built (zstd already removes the storage redundancy at 75–86×; wall upside is bounded and the "provably unchanged" stamp is its own poisoning risk).
- **Corpus arithmetic at the measured rate**: 50K pilot ≈ 2 days continuous at ~1,055 g/h; 500K ≈ ~20 days continuous (nights-only stretches beyond ADR-0004's 22–28-night assumption; the CPU-VPS contingency stands). Bytes: ~48 KB/game → 500K ≈ ~24 GB, well inside budget.
- **True pool baseline recalibrated**: heuristic-only w=16 is 1,248 g/h with randomized personalities (the ~2,300–2,900 estimate band was precon-derived, pre-personalities). Draw-clock/hard-cap tail is ~2% of games and is *not* convoke-driven (measured: convoke/improvise = 1.8% of records, deck-clustered, zero overlap with the 300 s+ tail); convoke stays a look-before-M2 flag.
- Mask consumers downstream (D4 pointer-decoder masking, D7 metric slicing, D8 executor) read the candidate-basis semantics from the schema doc; a payability *feature* can be approximated offline in Python if D7 wants the slice, without regeneration.
