# Collection / Incremental Mode — design sketch

**Status: PARKED CONCEPT (2026-07-18).** Not on any milestone. This file is the simmer
pot: brainstorm threads captured so design can continue incrementally without living
only in chat history. Promote to a real plan doc + ADR if/when it gets scheduled.

**One-line pitch:** a free-and-open-source gacha/incremental mode for Forge — build a
huge collection by opening tons of packs across Magic's ~million printings, unlock
increasingly weird high-paying autobattler formats, and let your decks earn currency in
the background by playing *real* headless games. The gacha itch, minus the wallet.

**Working codename: Chronicle** (chosen 2026-07-18, once the historical timeline
became the master structure — replaying the history of Magic as an incremental
collection game; on-the-nose bonus: Chronicles '95 is the mode's own canonical
market-crash event). Earlier candidates: Vault, Trove, Hoard.

## Relationship to existing Forge modes

Forge's **Quest Mode** has the closest shape: starter collection, real-edition
boosters with real collation, credits from AI matches, pack/singles shop.
**Correction (2026-07-18 archaeology): the "old and unloved" assumption was wrong —
both Quest and Adventure are actively maintained** (Quest core touched 2026-06, quest
content through 2026-07; Adventure has 1,200+ commits and very recent feature work).
Consequence: "replace Quest mode" is off the table — politically expensive and
unnecessary. **Verdict: Chronicle = a NEW mode built on the shared headless layers,
harvesting model code from both** (see the archaeology section below).

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

## Historical timeline (2026-07-18 addition — candidate master structure)

The mode recreates Magic's history: each player's game starts at year one (Alpha,
1993) and advances on its own clock, ~one release event per week (~130+ major sets ≈
2–3 years of content). Candidate *master structure* for the whole mode — it solves
the two hardest open problems (content-calendar authorship, volatility legibility)
with one move: **history is the content designer.**

- **The event calendar writes itself.** Chronicles reprint crash ('95, the Reserved
  List origin story), Fallen Empires overprint glut, Combo Winter ban wave, Mirrodin
  affinity bans, Modern Masters cycles — every market shock is a literal historical
  event. Perfects the "foreseeable-in-hindsight, not dice" principle: Magic-history
  knowledge becomes real speculation skill; for players without it, the mode is a
  history lesson taught through their portfolio.
- **Core fantasy: buy Power Nine at release prices.** The universal "if only I'd
  bought duals in 1994" counterfactual, playable. The endgame $1M trophy sits in the
  year-one shop for pocket change if you know to grab it. Probably the mode's
  strongest marketing hook.
- **Historical price data not needed.** Bulk historical price archives don't exist
  freely — but the structure dissolves the problem: today's real Scryfall prices are
  the *boundary condition the timeline converges to*, launch-era prices are MSRP-ish
  origins, and the event-driven + sim-meta-driven market generates the path between.
  Plausible-path, not true-curve.
- **Era-appropriate NPC metas = pipeline reuse.** Historical tournament decklists per
  era (Necropotence summer, Academy winter) via the mtgtop8 fetcher we already have;
  archives cover ~2000s+, pre-internet eras need light synthesis (Duelist-era lists).
- **Accidental onboarding solution.** Pool starts at ~295 Alpha cards and accretes
  complexity in deposition order (no planeswalkers until in-game 2007). Teaches
  30 years of accreted rules the way they actually accreted — a real pedagogy claim —
  and early-era pools are simpler for the heuristic AI to pilot.
- **The endgame is the present.** Timeline decelerates as it approaches today and
  lands on real-time tracking of actual releases — Forge's normal upstream set
  cadence becomes the live postgame content feed; rarest-printing completion is the
  infinite tail.
- **Prestige:** standard shape = collection resets, meta-progress persists (unlocked
  formats, timeline speed, collector achievements). Flavor option: **alternate-history
  modifiers** as prestige runs ("Chronicles never happened", "no Reserved List") —
  replayability from divergence, not new content.

Timeline-specific caveat — RESOLVED (2026-07-18 archaeology): early-edition
collation data is complete; see the archaeology section.

### Era rulesets — feasibility tiering (2026-07-18 fork archaeology)

Default stance was "modern rules, historical pools" — but the fork dive shows era
*flavor* rulesets are far cheaper than assumed. Pin for ANY era ruleset: **current
Oracle wordings + era rules deltas + era pools** — never era wordings (functional
errata history is per-card data; do not attempt). Era-limited pools kill most
edge cases structurally: the rules deltas never meet the modern cards that stress
them.

- **Tier 0 — already in the engine, config only:** `GameRules.manaBurn`; full ante
  suite (`playForAnte`/`matchAnteRarity`/`anteIncludeBasicLands`, `Ante` is a real
  zone in the script language, Contract from Below / Darkpact / Demonic Attorney
  scripted); mulligan variants already pluggable (`ParisMulligan`/`VancouverMulligan`/
  `LondonMulligan` behind `MulliganService`). A "93/94 flavor" ruleset ≈ a config
  object + era deck-legality data. (Real ante returns in Chronicle; module-name
  collision with our Ante ledger is thematic, not technical.)
- **Tier 1 — cheap localized flags:** legend-rule variants (one method,
  `GameAction.handleLegendRule`); planeswalker damage redirection (mid-2010s slices
  only); pre-6th tapped-blockers-deal-no-damage (combat flag).
- **Tier 2 — the one real engine project:** combat damage on the stack (1999–2009).
  Central combat/priority restructuring, weeks + permanent test-matrix tax; also the
  heuristic AI doesn't know the era's signature sac-after-damage tactic, so
  implemented-but-unplayed-well it still flattens era flavor. Skippable v1; but it IS
  the 6th-era defining rule — decide late.
- **Tier 3 — don't:** full pre-6th fidelity (interrupts, batches, damage-prevention
  steps) = a second rules engine.
- **Upstream constituency:** "modern rules, era pools" exactly matches how the living
  Premodern and Old School 93/94 communities already play. Tier 0/1 work doubles as
  real-format support for them — a standalone prosocial pitch, same shape as the
  multilingual angle.

## Quest/Adventure archaeology + platform verdict (2026-07-18)

Three parallel fork dives (Quest mode, Adventure mode, supporting data systems).
Full agent reports summarized; key paths repo-relative to the fork.

### Verdict: new mode on shared headless layers; harvest both, base on neither

- **Not "replace Quest"**: Quest is alive (core touched 2026-06, content 2026-07;
  XStream save format at v13 with a long migration chain — a live user base).
- **Not "base on Adventure"**: Adventure is welded to libGDX scene/stage code and
  its overworld — machinery Chronicle doesn't want. But its *model layer* is the
  best harvest in the codebase.
- **The load-bearing shared layer is forge-core and it is fully headless**: the
  entire booster/sealed collation engine (`BoosterGenerator`, `UnOpenedProduct`,
  `SealedTemplate`/`SealedTemplateWithSlots`, `BoosterSlots`, `PrintSheet`) has no
  GUI dependency and is what BOTH modes already use. Chronicle uses it directly.

### What to harvest from where

- **From Adventure** (`forge-gui-mobile/src/forge/adventure/`): the economy model
  layer is clean plain Java over forge-core types, deliberately independent of Quest
  — `AdventurePlayer` (collection = forge-core `CardPool`, dual currency, buy/sell,
  per-deck loadouts), `RewardData` (rich filtered card-reward generator: edition/
  rarity/color/regex-text filters + probabilities), seeded-shop-stock +
  restock-reroll + per-shop reputation (`ShopData`/`PointOfInterestChanges`),
  price-list override machinery (`AdventureReadPriceList`), and the
  save-format pattern (`SaveFileData` key-value blobs with migration shims, zlib).
  **`SpellSmithScene` is literally an existing gacha card-puller** (pay gold/shards,
  filter, random pull, accept/decline) — upstream precedent that gacha-style
  mechanics are already accepted in Forge. `RewardScene` has the card-flip pack
  reveal UX.
- **From Quest** (`forge-gui/src/main/java/forge/gamemodes/quest/`): toolkit-agnostic
  inventory/shop-stock engine (`QuestUtilCards`), pricing (`ReadPriceList` +
  `QuestSpellShop.getCardValue`, sell-multiplier-grows-with-wins), set-unlock
  economics (`QuestUtilUnlockSets` — includes date-proximity set selection, directly
  reusable for "sets near year X"), XStream persistence pattern (`QuestDataIO`).
  Entanglements to avoid: the global `FModel.getQuest()` singleton and
  `GuiBase`/`SOptionPane` dialogs inside `buy()`/`sell()`/win-lose paths
  (a `HeadlessGuiDesktop` no-op stub exists as precedent for driving these headless).

### Data-layer findings (resolves several open questions)

- **Early-edition collation: COMPLETE.** Alpha/Beta/Unlimited/Arabian Nights/
  Antiquities/Legends/The Dark/Fallen Empires all carry era-authentic `Booster=`
  definitions — including the combined `UncommonRare` sheet for the single-print-run
  sets and `†` multi-art variant commons; starter decks in `blockdata/starters.txt`.
  676 edition files; the 487 without boosters are legitimately non-draft products.
  Era-authentic pack opening from 1993 forward works today.
- **Historical formats: SUBSTANTIALLY EXIST.** `res/formats/` has 1,313 definitions
  incl. **152 dated archived Standard snapshots back to 1995-01-10**, each with
  `Effective:` date, set list, banned/restricted (the 1995 file bans the ante cards —
  Chronicle's era rulesets would un-ban them). `GameFormat` has effective dates and
  date-ordered collections; only a small "format as of date X" resolver is missing.
- **Price ecosystem precedent:** Forge already net-fetches a card price DB
  (`all-prices.txt` from the forge-extras repo) **generated by
  `forge-gui/tools/scryfallPricesGenerator.py`** — the Scryfall-derived price channel
  exists upstream. Gap: name-keyed only, in-game credits, no per-printing
  granularity — Chronicle's per-printing price base is an *extension* of an existing
  pipeline, not a new one.
- **Multilingual: better than assumed.** Card-text translation infra exists for 8
  languages (`CardTranslation` + `res/languages/cardnames-*.txt`, ~218K lines:
  names/types/oracle), plus set-level `CardLang` metadata and flavor-name/variant
  parsing. The missing piece for language-constraint formats is per-printing language
  as *collection identity* — ownable-card identity today is name+set+artIndex+foil
  (art-index granularity already there; language would extend `PaperCard` identity).

### Remaining platform question

Where Chronicle's UI lives: desktop Swing (Quest-style, both UIs to maintain) vs
mobile libGDX (Adventure-style) vs shared `forge-gui` screens. Unresolved; note that
the deck editor is shared infra (`FDeckEditor`) either way, and Chronicle's economy
core should be UI-free from day one regardless (the harvested layers already are).

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
2. ~~**Quest-code archaeology**~~ DONE 2026-07-18 (see archaeology section):
   forge-core booster engine headless; harvest Adventure model layer + Quest shop
   machinery; new mode, replace nothing.
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
