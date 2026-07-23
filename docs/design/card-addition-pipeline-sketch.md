# Card-addition pipeline sketch (upstream-track, NOT urgent)

2026-07-23, from a planning conversation. Premise: if the model ever ships
in Forge mainline, Forge devs and the custom-cards community must be able
to add cards without us in the loop. Sketch of the tiers, their compute,
and the prerequisites. Nothing here is scheduled; the port itself
(see the mobile discussion, same conversation) sits behind strength
earning the right to ship, and breadth lands per ADR-0018 regardless.

## The three tiers

**Tier 0 — add a card, no training (per-card, any machine).**
What the model needs for a new card: (1) its text embedding — one forward
pass through the pinned encoder, appended to the cache; (2) its 25-dim
structured features — derived from the card script, free; (3) an ID
embedding row — COLD for a new card. Package shape: a `forge-anvil
add-card` CLI that parses the card script, runs a bundled quantized
encoder (or a hosted embedding endpoint — zero local compute), appends
cache + SA-vocab rows (append-only per the pinned rule; new SA strings get
untrained descriptor rows — same class as the measured 0.03–0.05% OOV).
Specs: CPU-only, ~4–8 GB RAM with a quantized encoder, seconds-to-minutes
per card. A full custom set ≈ minutes-to-an-hour.

**Tier 1 — validate without training (per-card, CPU, ~an hour).**
Optional `--validate`: force the card into N seeded games (heuristic
opponents; the harness machinery is exactly this), run the standing
checks — label-extraction zero-error, never-cast audit, veto telemetry on
the card's SAs, census vs baselines. ~300–500 games at heuristic CPU
throughput ≈ an hour on a desktop. Output: a telemetry report the author
attaches to their card PR. Model-in-the-loop validation also works on CPU
(42M params, ~50–150 ms/decision) at ~3–5× the wall clock, or trivially on
any small GPU.

**Tier 2 — light retrain (per-release, consumer GPU, hours).**
NOT per-card and NOT per-author — fine-tuning per submitter would fragment
the model artifact. The release maintainer batches accepted cards, then:
corpus extension featuring the new cards → warm-start BC refresh (10–50K
steps ≈ 15–60 min on a 24 GB GPU; batch-reduced fits 8–12 GB) → optional
short RL touch-up → versioned model release. Grindstone drills seeded from
tier-1 telemetry (never-cast / high-veto cards) are the natural targeting
mechanism. Model artifacts version against pool version — the same
dataset-boundary discipline as engine bumps.

## Prerequisites that make tier 0 actually work

- **ID dropout during training** (queued since the D5 null-text arm): the
  measured shortcut — ID embeddings crowd out the text channel (null-text
  −0.19pp) — means new cards currently lean on a channel the model barely
  reads. ID dropout trains the model to play cards from text+features
  alone, which is precisely the cold-start path. Graduates from QoL to
  REQUIRED at the first breadth chunk.
- **Cold-ID convention**: define the null/mean ID row for unseen cards
  (the CardEncoder's learned-null machinery is adjacent precedent).
- **Encoder choice revisit at packaging time**: Qwen3-4B is pinned for NN
  structure, but BGE-M3 (568M, measured statistical tie in-pool) would cut
  tier-0 compute ~7× and drop RAM to laptop-trivial. Re-encoding the cache
  is a text-channel dataset boundary → needs a BC refresh; decide when the
  port is real.
- **Decision-surface coverage caveat**: cards whose scripts introduce new
  DECISION SHAPES (new callback/answer patterns, not just new text) need
  engineering (bridge tags, realizer, possibly heads) before any training
  helps — the ADR-0018 "features before breadth" rule seen from the other
  side. Rare, and tier-1 telemetry flags them (fallback counts on the new
  card's windows).

## What "many cards need nothing" means concretely

The expectation to communicate upstream: cards mechanically similar to
known ones (new stat-lines, recombined keywords, reworded effects) should
play sanely at tier 0 once ID dropout lands — the text encoder gives a
semantic prior and the structured features carry the mechanics. Cards with
genuinely novel *strategic* texture will be mediocre until a tier-2 pass
that includes them. The heuristic AI remains the fallback for anything the
model serves badly — replacing it outright was never the plan; a
per-decision confidence gate (serve heuristic when the model is
out-of-distribution) is the obvious hybrid and worth its own sketch when
the time comes.

## The cadence argument: the hybrid gate is REQUIRED, not optional

(User, 2026-07-23.) Forge adds cards continuously — several per week, plus
prerelease teasers well ahead of full sets (e.g. a dozen Star Trek cards
landing months before November's full expansion), plus the custom-cards
community. Honest retraining is inherently batched (tier 2 = per set
release at the fastest). So there is ALWAYS a window where the pool
contains cards the model has never trained on, and the gate is what makes
that window safe. Mapping onto Forge's actual rhythm:

- **Teaser/weekly/custom cards** → tier 0 (+ optional tier 1): embedding
  appended, model plays the card from text+features where confident, gate
  hands the rest to the heuristic. Zero training.
- **Set release** → tier 2 batch refresh sweeps up everything added since
  the last one.

**The architectural gift: the gate already exists.** Per-decision
heuristic fallback has been a first-class bridge response with provenance
telemetry since M0 (`by=bridge` vs heuristic-fallback tagging;
`PlayerControllerAnvil extends PlayerControllerAi`, so declining to answer
IS the heuristic answering). Upstream, "confidence gate" is a serve-side
policy for when to decline — cold-ID card in the window, OOV SA
descriptor, entropy/confidence thresholds — not new plumbing. The open
design work is the gating heuristic itself and measuring the blend's
strength (gate-rate telemetry slots into the standing census).
