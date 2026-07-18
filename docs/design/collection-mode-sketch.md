# Collection / Incremental Mode — design sketch

**Status: PARKED CONCEPT (2026-07-18).** Not on any milestone. This file is the simmer
pot: brainstorm threads captured so design can continue incrementally without living
only in chat history. Promote to a real plan doc + ADR if/when it gets scheduled.

**One-line pitch:** a free-and-open-source gacha/incremental mode for Forge — build a
huge collection by opening tons of packs across Magic's ~million printings, unlock
increasingly weird high-paying autobattler formats, and let your decks earn currency in
the background by playing *real* headless games. The gacha itch, minus the wallet.

**Working codename candidates** (Magic vocabulary under the smithy umbrella, per house
naming): **Vault** (Mana Vault; the collection is the vault), **Trove**, **Hoard**.
Undecided.

## Relationship to existing Forge modes

Forge's **Quest Mode** is the skeleton: starter collection, real-edition boosters with
real rarity collation, credits from AI matches, pack/singles shop. It's old and
unloved (community energy went to Adventure Mode) — which is a *pitch advantage*:
"revitalize Quest mode with X" is an easier upstream sell than a brand-new mode.
Load-bearing feasibility question (unscoped): how much of Quest's
inventory/booster/shop machinery is reusable headless vs. welded to the Swing UI.

## The three pillars

### 1. Collection chase (the gacha half)

- Forge's card DB already models editions, arts, rarities, promo/flavor variants
  (cf. the Universes Within `Variant:...FlavorName:` class from the DC pool pipeline).
  Pack opening with authentic collation already exists. The printing-variant space is
  real data, not vaporware.
- Missing piece is collection **UX**: binder views, per-set completion, "new card!"
  reveals, pity timers, duplicate protection.
- **Ethics stance:** keep the collection/anticipation loop, drop the extraction. Pity
  and dupe protection are player-friendly *defaults*, not engagement traps. Being the
  game that does pack-opening ethically is part of the identity.

### 2. Idle battler (the incremental half)

- **The backend is substantially already built.** The Anvil batch harness runs
  headless AI-vs-AI Forge games at ~1,500 g/h on desktop hardware, `nice -19`,
  graceful stop/resume. "Your decks battle in the background earning currency" =
  real games actually played, not a faked abstraction. No commercial idle game can
  claim its numbers are real.
- Earning rate ≈ payout multiplier × measured winrate × games/hour. Slower formats
  (multiplayer pods) self-balance on games/hour.
- Cheapest prototype in the whole concept: wire `harness launch` to a Quest inventory
  and a credits formula, pure heuristic AI, zero ML. A weekend spike.

### 3. Deck judge (the ML tie-in)

- Mirrors Anvil's core invariant (*the engine adjudicates every claim a learned
  component makes*) as a game mechanic:
  - **Instant estimate:** learned deck-quality score on deck save (eventually Tutor's
    evaluation half). Fast, but a claim.
  - **Background verification:** the idle layer plays real games; measured winrate
    confirms or corrects the estimate, visibly ("Tutor predicted 55%, you're at 62%").
- **Ante integration:** surface the luck ledger to players — "you went 2-8 but
  corrected winrate says the deck is fine, you got mana-screwed." Solves the
  idle-game frustration of variance masking progress, with real statistics.
- Naturally the *last* pillar to build; the mode works without it.

## The constraint ladder (the core progression design)

A long ladder of unlockable sub-formats with escalating constraints and payouts.
Netdecked Legacy = the consistent low-tier income floor; the high-paying formats are
weird and obscure — e.g. more currency from 45% winrate on a bracket-3 5-player
Commander deck restricted to Japanese full-art printings than from a 90% stomp.

Why this works (it solves three problems at once):

1. **Makes the collection mechanically load-bearing.** If formats gate on
   *printing-level* properties (set, frame, art treatment, language), variants stop
   being dead cosmetic pulls and become progression keys. Closes the loop:
   battler → currency → packs → collection depth → format unlocks → better earning.
   This is exactly the incremental-genre generator structure (each format = a
   generator with unlock condition, cost basis, rate) mapped onto Magic natively.
2. **Solves netdecking structurally, not punitively.** You can't netdeck into a
   format whose pool is what *you own* within a constraint set. High tiers are
   deckbuilding puzzles — the fun part of deckbuilding.
3. **Huge combinatorial content space.** Cross: Forge's supported formats
   (multiplayer AI, Commander variants, Archenemy, Planechase, Vanguard, Momir, …)
   × opponent strength tiers × real-world-cost layers (budget/pauper-style)
   × theme layers (tribal, color identity) × art/printing layers (full-art, frame,
   language, era). Thousands of plausible "tournaments" from crossing existing axes.

**Rotation:** weekly/monthly rotating earning bonuses over sub-formats — cheap
replayability lever over the same combinatorial space; keeps the ladder from being
solved once. Important because a shallow collection mode gets boring fast if the
pack-opening curve is even slightly off (see Risks).

**Checkpoint bosses:** Anvil RL checkpoints are a shelf of graded-strength agents
produced as a research byproduct — an escalating opponent ladder with provenance at
zero content cost. (Convergence: ADR-0018 classifies 4-player as a *feature* on
Anvil's roadmap; this mode wants the same multiplayer bridge coverage. Tracks feed
each other.)

## Empirical economy calibration

Payout multipliers don't need hand-tuning: run a few-thousand-game headless sweep per
format/tier (an overnight batch job on existing infrastructure) to measure baseline
winrates and game durations, and set rates from data. Re-run the sweep when a set
drops. The economy balances against reality — and the "idle game whose numbers come
from actual simulation sweeps" claim holds all the way down.

## Multilingual / printing metadata

- The Japanese full-art constraint class is real: a bunch of arts exist *only* on
  Japanese printings. Forge's data model is English-centric and mostly lacks
  language-level printings.
- Two-step path: (a) near-term constraint axes use what Forge already encodes (set,
  rarity, frame, promo/flavor variant); (b) **extend Forge's multilingual/printing
  support** via a Scryfall bulk-data import (every printing with language, frame,
  treatment — pipeline shape and size of the DC pool fetcher). Framing note: (b) is a
  prosocial standalone upstream contribution independent of this mode — worth doing
  on its own merits and pitching that way.

## Market / trading layer (2026-07-18 addition)

Second player fantasy alongside the gacha: substituting for cracking packs *to
resell* — pull-jackpot and card-trading gameplay, no real money anywhere.

- **Price base = real prices, stretched.** The Scryfall bulk import (already queued
  for printing/multilingual support) carries per-printing market prices — snapshot at
  import as the base layer, free. Stretch transform: exponent >1 in log-space blows
  the tail out (top cards → ~$1M) while barely moving the bulk; real prices are
  roughly power-law so the exaggerated tail = an exponentially deep progression
  ladder, exactly the incremental-genre number spine. The $1M card is the endgame
  trophy.
- **Market and rotation are ONE mechanism.** Rotating sub-format bonuses are demand
  shocks: rotation week spikes both earnings and the prices of the printings it
  gates on, because they share a cause. Partially-telegraphed rotation calendar
  ("spoiler season": rumors → announcements) yields speculation gameplay for free —
  buy ahead, sell into the spike. Trader archetype emerges from an existing system.
- **Prices driven by real simulated results.** Real Magic prices move on tournament
  results; ours can move on *actual* headless tournament results — the empirical
  calibration sweeps already measure meta share and winrates per format, so demand
  derives from measured performance. The "numbers are real" pitch extends to finance.
- **Real MTG-finance dynamics, all simulatable, all on the content calendar:**
  reprint crashes (calendar set releases reprint staples), banlist shocks,
  buylist-vs-market spreads, theme-collector NPCs who overpay (arbitrage minigame),
  and market-cornering on obscure printings as an achievable incremental goal.
  Counterparty problem (offline single-player) → NPC vendors + simulated global
  market; no online trading.
- **Ante finance ledger (the prosocial angle):** track lifetime pack EV vs realized
  pulls. Cracking packs for EV is -EV gambling in real life; the ledger demonstrates
  the house edge with the player's own data at zero real-money stakes, while jackpot
  moments stay fun. Keeps the ethics stance coherent as the mode gets more
  casino-shaped: money fake, math shown.

Market-specific cautions:

- **Income-balance dominance:** if trading out-earns the battler, optimal play stops
  playing Magic. Viable archetype yes, dominant strategy no — calibration sweeps can
  measure cross-archetype income rates, but it needs a design eye.
- **Volatility tuning is the new pack curve:** too random reads as slots, too
  predictable and speculation is solved. Principle: anchor shocks to legible causes
  (rotations, reprints, meta results), never pure noise — losses should be
  foreseeable-in-hindsight, not dice.

## Risks / honest caveats

- **Scope:** a whole game mode beside an RL research program, competing for the same
  nights-and-weekends hours. Mitigation: decomposes into independently shippable
  chunks (below), grown ADR-0018-style in small increments.
- **Pack-opening curve fragility:** the named killer. A shallow or mistuned
  acquisition curve bores players quickly; the combinatorial format space + rotation
  is the hedge, and empirical calibration is the tuning instrument — but curve design
  still needs real care (this is where commercial gachas spend their whole design
  budget).
- **Upstream buy-in:** float the concept in Forge Discord before writing code (same
  playbook as the manabrew collaboration). Design conversations go in PRs/Discord,
  never issues.
- **Heuristic-AI pilot quality in weird formats:** measured winrates are vs. AI in
  the same format, so it's symmetric — but the AI playing jank badly compresses tier
  separation. Watch, don't pre-solve.

## Staging sketch (cheapest-first)

1. **Idle battler spike:** harness → Quest inventory → credits formula. Heuristic AI
   only, no UI beyond numbers. Proves the loop.
2. **Quest-code archaeology:** scope headless reusability of inventory/booster/shop.
3. **Constraint-format engine:** deck-legality predicates over existing Forge
   metadata; first short ladder; empirical calibration sweep.
4. **Collection UX:** binder/completion/reveal/pity. Biggest lift.
5. **Scryfall printing import / multilingual support** (standalone upstream PR track).
6. **Rotation system;** checkpoint-boss ladder.
7. **Deck judge + Ante surfacing** (post-Tutor).

## Related

- Sibling side-project concepts: Grindstone drill economy (design §6), daily puzzles.
- Anvil design doc §8 (pool), DC pool pipeline (fetcher patterns for Scryfall import).
- ADR-0018 (features-before-breadth roadmap rule; 4-player classified as a feature).
