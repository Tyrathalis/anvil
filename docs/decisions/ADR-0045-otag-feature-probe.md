# ADR-0045: Oracle-tag functional-feature probe — negative for the critic path; function is unencoded but not the missing signal

- **Date:** 2026-08-08
- **Status:** accepted
- **Design-doc anchor:** §1 (card encoder), §5 (Tutor — rider note)
- **Inputs:** outside-builder observation (talor, Discord: otag-enriched
  embeddings cluster function far better — Basalt Monolith "untap" →
  "artifact ramp/combo"), [ADR-0043](ADR-0043-b1-feature-probe-verdict.md)
  (probe machinery + the reconstruction diagnostic),
  `data/runs/otag-probe-v1/` (tag table + features + report of record).

## What was built (cheap, CPU-only, ran beside the label campaign)

`scripts/otag_probe.py` (Scryfall official `otag:` searches → 27/35
candidate tags resolved, 1,138/1,701 pool cards tagged) +
`anvil/encoder/otag_features.py` (30 features: 10 functional groups ×
{self hand, self battlefield, opp battlefield}, info-set-respecting,
count-capped) + `feature_probe.py` generalized to probe any feature
bundle (`--features-npz`/`--report`) through the identical frozen-
benchmark split/CV/ridge.

## Findings (c2; state baseline reproduces 0.4552)

1. **No lift, any family.** Best `state+obfopp` 0.4509 (−0.004);
   `state+all` 0.4366; hand-outs alone Spearman −0.075 (weakly
   ANTI-correlated in the loss-adjacent population — holding interaction
   while dying); feats-alone 0.14.
2. **The reconstruction shape DIFFERS from B-1:** `[STATE]` decodes the
   functional counts at **median R² 0.26** (vs 0.65 for B-1's
   arithmetic) — worst on combo/wipe/counter presence (0.03–0.07).
   So: **function is largely NOT in the representation (talor's
   clustering observation replicates at our trunk), and yet function is
   ALSO not the missing live-vs-dead signal.** Two questions this probe
   cleanly separates; B-1 answered the first differently (encoded) with
   the same second answer (not the signal).

## Decisions

1. **Otag features do NOT ride the graduated bundle** (aggressive-
   inclusion registry: probe not cleared).
2. **Otag text enrichment gets no priority for B-3** (if it ever
   unparks): enriching what the embedding says about function would fix
   a real representation gap that this probe says does not pay for the
   critic. The pool-expansion caution STANDS strengthened (the trunk
   under-represents function — generalization to new cards through
   text embeddings remains suspect); the fix simply is not on the
   ranking critical path.
3. **Rider for Tutor (§5):** deck co-occurrence similarity (the other
   half of talor's artifact) is a synergy prior — filed as a Tutor
   asset, not a pilot lever.
4. The residual 0.46→0.9 signal is still unlocated: not state
   arithmetic (B-1), not functional composition (this), partially
   reachable by trunk gradient (B-2). Hidden-information headroom is
   the next unpriced axis — the full-vis-vs-masked unfreeze probe
   (queued post-campaign) prices it.
