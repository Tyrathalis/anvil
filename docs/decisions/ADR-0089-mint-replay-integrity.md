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

- **ADR-0078 contamination flag (honest, small):** the ceiling sweep
  used the same mark-consuming machinery, so in multi-fork games every
  fork after the first certified a re-rolled mainline (~15–20% of the
  600 sweep turns at 1.2 turns/game). First-fork turns and single-fork
  games are clean; the FUNDED verdict's ~6× margin dwarfs the slice,
  but the read of record now carries this asterisk. Any re-run of the
  sweep machinery inherits the fix.
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
