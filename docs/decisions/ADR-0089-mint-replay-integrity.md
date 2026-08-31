# ADR-0089: mint replay integrity — two stacked divergence mechanisms found and fixed by the parity witness; the Obs.mark seq fix (fork commit `f9eadfa8d4`)

- **Date:** 2026-08-31
- **Status:** accepted
- **Design-doc anchor:** executes ADR-0088's mint under its own parity
  standard; supersedes the ADR-0088 addenda's mechanism attribution
  (the addenda's FIXES stand; the primary mechanism was deeper)

## Context

The ADR-0088 mint replays model-generated stores to certify schedule
arms at the states the policy actually visited. Its parity witness
(obs decision-stream comparison, standing rule) failed the first run
and then the phased rerun. Forensics across the two failures found
**two independent mechanisms stacked**, one ours-architectural, one a
five-milestone-old convention colliding with a three-milestone-old
convention.

## Mechanism 1 (serve-side): carry-key collision across stores

`SchedServe` state is keyed `(g, seat)`; both init-ckpt stores span
games 0–239. Concurrent cross-store replay clobbered carry constantly,
flipping answers at emission windows (the run-1 signature included
divergences BEFORE any fork — impossible for mechanism 2). **Fix:
phased-by-store lanes + a fresh server per phase**, now owned by the
generated `run-lanes.sh` itself (also covers warm-server lane reruns).
Durable fix routed by name: channel-keyed carry (serve hardening).
Real, fixed, but NOT the primary driver of the phase-1 failure.

## Mechanism 2 (the deep one): Obs.mark consumed a decision seq id

- M2 D4 designed fork MARK records to share the decision seq counter
  (so marks order among decisions positionally — correct for
  rollout-label generation, where the mainline is itself the data).
- M2 D6 keyed the serve's sampling noise `noise_seed(game_seed,
  dec["s"])` — replay-stable in every workload where the replay's obs
  stream matches generation's.
- The mint is the first workload to replay a **fork-free generation
  under fork-bearing replay**: each fork point wrote a mark, consumed
  one id, and shifted every subsequent mainline decision's `s` by +1
  per fork — so every post-fork decision drew DIFFERENT sampling noise
  than generation and re-rolled. Divergence followed at the first
  tie-prone decision (own-seat cast windows).
- Measured signatures, all explained: s-offsets of exactly {0,1,…,n}
  across a game's n fork points, content-aligned until a re-rolled
  choice flips; divergence pinned at/after first fork turns; the solo
  single-fork smoke structurally blind (early-stop cut the stream
  before any re-rolled decision).

**Fix (fork commit `f9eadfa8d4`): `Obs.mark` carries the next seq as
an order stamp without incrementing** — decision numbering becomes
fork-invariant. Nothing reads `mark.s` (verified: readers use record
position `_pos`); game path untouched.

## Jar drift, recorded and proven

The fixed jar (`fe58d51745…`) replays stores generated on the cousins
jar (`935c2e8e40…`). `sched_mint.py lanes --allow-jar-drift <reason>`
records the pair in the manifest; **the parity witness on every
replayed game is the ADR-0025-standard empirical proof** of game-path
identity (strict compare, s included — the witness passing on
multi-fork games is only possible if both mechanisms are dead).

## Consequences

- **ADR-0078 VERIFIED IMMUNE (corrected same day — the first draft of
  this ADR flagged it as contaminated):** the s-shift changes behavior
  only under SAMPLED serving (`noise_seed` feeds the Gumbel draw;
  argmax never reads it). The ceiling census was generated on the
  iter-019 **argmax** server (devlog 2026-08-25 session 4: ":50065,
  the final_read serve convention") and the sweep replayed under the
  same convention ("margins byte-identical across the re-run" — only
  possible under argmax). Two independent corroborations: the sweep
  lost only 17/600 turns where the mint's diseased runs truncated ~10%
  of theirs; and its stage-2 pairing was internally consistent
  throughout. **The mint is the FIRST sampled replay in project
  history** — probe stores are temperature-1.0 behavior-policy data
  and can only be replayed sampled, which is why the latent collision
  fired here and never before. Any future sampled-replay instrument
  requires the fixed jar (`f9eadfa8d4`+).
- Standing rule born (→ standing-rules.md): **every input to the serve
  path must be replay-stable, and the obs seq is a serve input** (the
  noise key rides it) — any machinery that adds/removes obs records
  relative to generation shifts the policy itself, not just
  bookkeeping.
- The parity comparator's three outcomes stand: EXACT / exact-but-
  truncated (counted) / MISMATCH (fatal).
- Cost of the episode: ~2 discarded lane-days of nice-19 compute, one
  fork commit, and the mint restarting from zero rolls — against a
  counterfactual where ~1,000 labels minted from re-rolled states
  trained probe3's primary decode signal invisibly.
- The mint relaunches on the fixed jar after a multi-fork solo smoke
  passes the strict witness (content AND s exact through all fork
  turns).

## Addendum (same day): the residual — sparse concurrency flips, salvage-by-prefix

With both mechanisms dead, the fleet's early-parity gate still showed
**sparse late flips** (2 of the first 3 games, at dec ~650 and ~1,200;
s-offsets ZERO — the mark fix holds through 8 fork turns in one of
them). Signature: a single decision re-answered at a mid-turn
carry-consuming ask, ~1 per ~1,500 decisions, under fleet load only
(solo replay byte-exact over ~5k decisions). Ruled out: eviction (cap
4096 vs ~22 live keys), decode sampling (greedy), noise keys (s
matches). Remaining suspect: sub-ULP logit variation under concurrent
batching or a rare serve-path race — **routed by name with the
channel-keyed-carry item as the serve-determinism hunt**.

Resolution: **salvage-by-prefix semantics** in the parity verb — per
game, fork turns strictly before the first divergence certify
witnessed-exact states and are VALID; later turns are dropped;
`finish` refuses to run without the witness's `valid-turns.jsonl` and
drops unwitnessed positives loudly. A **survival-rate floor (<50%
valid ⇒ FATAL)** keeps the verb sensitive to any systematic-defect
recurrence — sparse flips cost yield, first-fork-pinned divergence
still stops the mint. The running fleet's data is salvageable under
these semantics (pre-flip forks were always exact); no third restart.
Expected yield impact: roughly 20–35% of turns dropped ⇒ ~650–800
labels; the k=4 fallback covers the low end.
