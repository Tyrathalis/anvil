# Collection / Incremental Mode — design sketch

**Status: SCHEDULED (2026-07-31,
[ADR-0029](../decisions/ADR-0029-chronicle-scheduling.md)).** The promotion rule
fired: implementation plan lives at
[chronicle-mvp-plan.md](chronicle-mvp-plan.md) (playable-branch side stream;
M4 keeps the research hours). This file remains the canonical design record —
design changes still land here or in ADRs, implementation staging lives in the
plan doc.

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

## Structural design v0 (2026-07-20)

Priority order (user): collector / incremental / deckbuilder / trading. **Master
structural move: the four layers unlock in the order they historically emerged —
Magic's own history built them in exactly this priority order, so the timeline IS
the tutorial.** 1993: packs + kitchen table (collector). Months in: the secondary
market appears as the game explodes (trading seed). '94–'95: organized play +
formats formalize (venues, deckbuilder). '96: Pro Tour era (high circuits).

**Frame:** home screen = the binder, not a battlefield. Narrative voice = a period
trade paper, *The Chronicle* (mode name doubles as the in-fiction newspaper): every
simulation output arrives as news — spoilers, banlists, reprint bombshells, meta
reports written from actual headless tournament results, price movers. No system
logs; the trade press of the year you're living in.

**Two clocks.** Timeline clock: in-game date advances at a player-owned cadence
(default ≈ one release cycle per real week; pausable, adjustable — the player owns
their clock; no engagement traps). Income clock: real time — the idle battler plays
real games while away. Wall-clock feeds earning; the timeline never punishes absence.
*(Amended 2026-07-31: the timeline clock is now keyed to played days — see "Daily
gacha structure v1" below. The two-clock split itself survives unchanged.)*

### Layer 1 — Collector (the core loop)

- **The in-print shelf**: products purchasable at MSRP-ish prices ONLY while
  historically in print; Alpha is on the shelf for weeks, then market-only forever.
  Print runs + rotation = the scarcity engine; "I was there" delivered mechanically.
- Era-authentic collation (data confirmed present); duplicate protection = explicit
  settings knob, never hidden manipulation.
- Completion per set/master-set, reveal moments, chase trophies, oddity achievements
  (all † variants of FEM, etc.).

### Layer 2 — Incremental (the engine)

- **Venues** unlock along the historical organized-play arc: kitchen table → store
  league → regionals → Pro-Tour-era circuits; format circuits appear on their real
  birthdays. Assign decks; headless games run for real in the background.
- Income = venue multiplier × measured winrate × real games/hour − entry fees (the
  risk/reward knob); prizes partly IN PRODUCT (historically accurate; feeds layer 1).
- Generators = concurrent tables, venue tiers, prize multipliers.

### Layer 3 — Deckbuilder (the skill expression)

- Venue gauntlets = era-real decklists under the dated format snapshots; the gate is
  the deck's MEASURED performance, never an abstract collection-power stat.
- Constraint tournaments on top: market-priced budget caps ("$50 deck at 1996
  prices" — trading feeds deckbuilding), tribal/era/printing constraints, rotation.
- Pre-Tutor deck judge = **sim probe**: a quick headless burst estimates winrate
  before entry fees are committed; Tutor's learned scorer later makes it instant,
  with the battler as the standing auditor (the engine-adjudicates invariant).

### Layer 4 — Trading (the economy)

- Secondary market EMERGES in the timeline's first months (it didn't exist at
  launch) — historically accurate and the natural unlock gate.
- Buylist (instant, wide spread) vs market (better price, slower); speculation on
  telegraphed events; **market-depth limits** (dumping 40 Lotuses moves the price —
  which makes cornering obscure printings a real strategy); Ante finance ledger for
  pack-EV honesty throughout.

### Cross-cutting

- **Manual play optional everywhere**: take control of any battler game or venue
  final for an earnings bonus; never required. Chronicle is a collection game that
  *contains* Magic — Forge proper serves the people who mainly want to pilot.
- Loops by scale — minute: open/sort/list/browse shelf; session: collect income →
  read the new Chronicle issue → trade the news → reassign venues → tweak decks;
  week: release event (spoiler → prerelease → shelf turnover) + rotating constraint
  purses; era: format births + historic shocks + mastery; run: decelerate into the
  present → live postgame → prestige ("New Collection" runs, alt-history modifiers).
- Module skeleton (all UI-free per the platform verdict): timeline service (date,
  release calendar, event feed, as-of-date format resolver), collection service
  (printing-identity inventory over forge-core CardPool), product service (in-print
  shelf + collation + era MSRP), market service (anchor-interpolated event-driven
  prices, buylist spread, depth), battler service (venues, era gauntlets,
  results→income), Ante ledger, news generator (everything → Chronicle issues),
  binder-first libGDX screens.

## Daily gacha structure v1 (2026-07-31 — Pocket lens; user decisions pinned)

Design session applying the Pokémon TCG Pocket lens to the sketch. What the lens
adds is the discipline the sketch was thinnest on: **session shape and pack
scarcity**. What Chronicle has that Pocket doesn't: the history walk is a
**pre-authored live-ops calendar** — Pocket pays a design team to manufacture a
novelty beat every ~6 weeks; Magic's history pre-recorded ~30 years of them.
Framing (user): looping through the actual release history *as though it had been
a mobile gacha all along* is itself the alternate way to experience the game.

- **Early Magic sets are Pocket-sized.** Arabian Nights 78 cards, Antiquities
  ~100, Alpha 295 — Pocket's discovery that small completable sets drive
  collection satisfaction is built into Magic's deposition order, and set size
  grows as player capacity grows.
- **The chase-treatment ladder is historical.** Pocket sustains chase after
  playset completion via parallel treatments; in Chronicle the treatments get
  *invented on screen* — foils arrive in 1999 as an in-game event, mythics 2008,
  masterpieces 2016, showcase frames late-game.
- **The daily story beat is real.** The Chronicle issue (news, spoiler rumors,
  price movers, your venue results as the sports section) is a daily narrative no
  commercial gacha can match, because theirs must be written.

### Pinned decisions (2026-07-31, user)

1. **Timeline clock = one tick per played day.** A day you open your packs is an
   in-game day; a day you skip simply doesn't happen in 1994. No banking
   machinery, no binge-forward, no absence punishment — the daily ritual cadence
   without the FOMO trap. In-game events run mostly on 7- and 30-day schedules
   (release cycles, tournaments, market arcs). The two-clock split survives: the
   idle battler stays on wall-clock, income accrues while away.
2. **Run length ≈ 2–3 years of played days** (~one release cycle per played
   week, decelerating into the present-day live feed as the endgame).
3. **Acquisition channels — ration the shelf, randomize the rest:**
   - *Free daily ration* — a few packs, player's choice among in-print products.
   - *The LGS* — cheaper packs and boxes, **rotating randomized stock** (the
     daily stock roll is itself a check-in hook; harvest Adventure's
     seeded-shop-stock + restock-reroll machinery, already identified in the
     archaeology).
   - *Trading sites* — randomized offers: recent product marked up, or
     older/out-of-print sealed at market price (cracking an out-of-print box =
     the high-roller jackpot moment, EV ledger visible).
   - *Tournament prizes in product and cards* — scarce-but-grindable channel
     that deliberately does NOT flow through the market.
   - *Singles market* — present but **deliberately slow** (next pin).
4. **The slow singles market is the load-bearing scarcity lever.** With ~a
   million printings, even 20 packs/day is a long collection arc — the
   incremental layer is *allowed* to scale pack throughput for all-in players
   (good decks → tournament income → more packs), and openings stay exciting
   because singles are NOT the efficient path around them: cards take
   unrealistically long to enter the singles market after release
   (historically grounded — the secondary market really did lag), listings are
   thin (depth limits already in the market section), and late-game price
   scaling can stretch further if needed. Packs first, singles as the
   completion tail — the inverse of real-world TCG economics, on purpose.
5. **Dupe protection: not needed.** The simulated market IS the dupe value
   (auto-buylist toggle); a dead pull is impossible because trading is a pillar.
6. **Pity: deferred, not designed in.** Sell-and-buy-singles already bounds bad
   luck; if a legible promise turns out to be needed, the elegant skin is
   **per-product store credit** (opening packs of a product accrues credit
   redeemable against its singles — pack points mechanically, a vendor
   relationship economically, so it coexists with the market instead of
   duplicating it).

### The daily session script (the session contract)

Pocket's real lesson is a *contract* about session length: minutes minimum,
depth optional. Chronicle's script: read the paper → collect battler income →
**open the ration** (the centerpiece reveal — Adventure's RewardScene flip is
the seed, Pocket's rip is the bar) → check LGS stock roll + trading-site offers
+ market tick → optional depth: board puzzles (`res/puzzle` framework exists),
pilot an individual duel or match, adjust built decks, refresh which decks sit
in which tournaments.

### The tournament board (constraint ladder, concretized)

Standing surface: **many tournaments open at once, only a couple paying well,
and the well-paying ones are usually weird gimmick tournaments requiring
highly-specialized decks** (the sketch's constraint ladder + rotation collapsed
into one legible UI). The board rotates on the 7/30-day event schedules; prize
support in product/cards makes gimmick specialization pay in scarcity, not just
currency. Trade night rides the same cadence: weekly NPC collectors visit with
generated binders and biased valuations — the wonder-pick analog and the
theme-collector arbitrage minigame unified.

### Round-2 refinements (same session, user)

- **Pack math & cadence:** an MTG booster is ~15 cards (and the earliest small
  sets — Arabian Nights, Antiquities, The Dark, Fallen Empires — shipped 8-card
  boosters: historically authentic AND Pocket-sized, so the early-game ration
  feels right with zero tuning), so even 2 packs is a big reveal next to
  Pocket's 5-card packs. **One opening per played day gets full value** —
  deliberately kinder than Pocket's 12h/24h split timers; no second check-in
  required or rewarded.
- **Bulk lots = the late-game bulk UX answer:** unsorted bulk purchases
  (thousand-card lots, expected mostly bulk) with a collection-diff-aware
  reveal — rapid scroll that pauses only on cards you don't own or above a
  value threshold. Lots draw from *circulation* (older cards), packs from
  *print sheets* — mechanically distinct acquisition distributions; the EV
  ledger covers lots too (a different gamble shape, shown honestly).
- **MVP: the idle battler is NOT in the vertical slice.** Opening and
  collecting must be fun alone; MVP = timeline + in-print shelf + pack ritual
  + binder + paper stub. Tournaments/battler layer on afterward (staging
  sketch reordered below).
- **Normalized release cadence:** real-history ORDERING, not real-history
  pacing or print windows. Fixed release cadence (~one release event per
  played week, per the run-length pin); shelf windows normalized to standard
  durations, with historical *character* kept as deliberately tuned exceptions
  (Alpha/Beta short and scarce, FE/Chronicles long and glutted) rather than
  simulated fidelity. The tick→game-time mapping table dissolves; the
  remaining content task is **curating the master release list** (draftable
  expansions in order + notable supplemental products as special events).
- **Circulation-based singles ADOPTED, tuned slower than the player.** The
  fiction: the late-game player is ahead of the curve — few others crack much
  product early in a release. Consequences: the newest sets are pack-only in
  practice (the desired scarcity, with a causal story); the player becomes a
  *supplier* on recent sets (their sales are a real fraction of circulating
  supply, so market-making and cornering emerge naturally rather than being
  scripted); older sets deepen into a genuine singles market over time.

### Collectible identity — "what is a card" (opened 2026-07-31, discussion live)

What one collection entry IS, decided before the MVP inventory schema exists:

- **Working proposal: identity = (oracle name, set, collector number, finish)** —
  i.e., a Scryfall printing × finish — with **language reserved as a later
  extension** (the multilingual import is already a queued track; schema leaves
  the field). Forge's current ownable identity is name+set+artIndex+foil; the
  proposal is a modest extension of it.
- **Quality grades / condition: user leans AGAINST as an identity axis; noted
  for discussion, not closed.** Against: condition is scarce physically because
  cards degrade — in a digital sim it's a fake axis that multiplies inventory
  ~6× and prices, not gameplay. For (the honest counter-case): the circulation
  model could generate the *real* collector dynamic where NM copies of old
  cards get scarce over time, and grading/slabbing is a plausible late-game
  minigame. If deferred, the compromise shape is: condition lives on **market
  listings and bulk-lot contents** (default NM from packs), never on inventory
  identity — schema keeps that door open without paying the 6×.
- **Test cards / oddities:** things that ARE real printings in the data
  (prerelease promos, judge foils, Mystery Booster playtest cards, serialized
  cards from 2022 on) come along free with the Scryfall import and slot onto
  their historical dates. True oddities NOT in the data (internal test prints,
  miscuts, Summer Magic-class stories) should be **scripted trophies and
  bulk-lot flavor finds, not identity axes** — content, not schema.
- **Serialized (2022+):** the modern-era endgame chase arrives on schedule via
  the timeline; identity-wise it's a printing like any other plus a number.

### Consequences / open threads

- Platform lean (libGDX, mobile-first) *strengthens* — a 5-minute daily ritual
  is a phone gesture.
- Ethics pitch sharpens: "the daily gacha with no FOMO" — played-day ticks,
  no banked-reward pressure, visible EV ledger, no wallet.
- **Bulk-opening UX is a new problem Pocket doesn't have:** at 20 packs/day the
  one-by-one rip gets old, but the jackpot moment must survive — needs a
  fast-open/box-crack mode with a highlights reel (design before the reveal UX
  is built, not after).
- **Staging order question (open):** the Pocket lens suggests the vertical
  slice may be timeline + shelf + pack ritual + binder + paper stub
  (collector-first, matching the user's priority order) rather than the idle
  battler spike the staging sketch leads with.
- Tick→game-time mapping needs a real table: release density is wildly uneven
  (1993–94 sparse, 2020s firehose) and the deceleration curve interacts with
  the 7/30-day event schedules.

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
mobile libGDX (Adventure-style) vs shared `forge-gui` screens. The deck editor is
shared infra (`FDeckEditor`) either way, and Chronicle's economy core should be
UI-free from day one regardless (the harvested layers already are).

**Upstream UI-activity read (2026-07-18):** no large UI modernization program exists;
desktop Swing gets maintenance + small QoL (autotap highlighting, deck sleeves,
window-ownership fixes), while *platform investment* flows to the libGDX frontend —
open PR #11190 adds **iOS support** (JvmDowngrader/MobiVM pipeline), Adventure gets
feature PRs (Randomizer/Archipelago #11167). The libGDX UI already runs on desktop
via `forge-gui-mobile-dev`. **Lean: build Chronicle's UI on the libGDX frontend**
(one codebase → Android + desktop + future iOS, and the Adventure UX pieces we'd
harvest — RewardScene reveal, SpellSmith — are already there). Watch item:
PR #11093 "Replace Scryfall's API with custom API using Scryfall data" — directly
relevant to the printing/price import plans.

**Related prosocial candidate — Android asset delta updates:** the ~160MB assets.zip
full redownload every app update is by design (APK is ~12MB code-only; all of `res/`
ships as assets.zip versioned in lockstep with the app — `AssetsDownloader` compares
`assets/version.txt` + res `build.txt` against the APK and prompts, mandatory when
build dates mismatch, because card scripts are engine-coupled). There is NO delta
mechanism — a manifest/per-file-hash incremental updater would cut typical updates
to a few MB. Self-contained, user-popular, and Chronicle-relevant (a collection mode
is res-heavy).

## MVP slice spec v0 (2026-07-31, decisions pinned same session)

Scope pins (user): **content window 1993–94, Alpha→Fallen Empires** (~9 booster
releases + starter decks ≈ 2+ months of daily play at one release per played
week; Chronicles and its crash deliberately held for the market stage);
**economy = thin + daily stock roll** (static rarity/era-flat buylist for
selling dupes, LGS purchases, seeded randomized daily stock — no circulation
model, no dynamic prices); **kitchen-table play = stretch goal** (build only if
the slice lands early); **identity confirmed = printing × finish** (language a
dormant schema field; condition never in identity; finish axis ships dormant —
no foils until 1999). Foils, battler, tournaments, market/circulation, trading
sites, bulk lots, trade night, puzzles, prestige, languages: all explicitly OUT.

Window products in order: Alpha, Beta, Unlimited, Arabian Nights, Antiquities,
Revised, Legends, The Dark, Fallen Empires — all with confirmed era-authentic
collation (8-card boosters for ARN/ATQ/DRK/FEM, UncommonRare combined sheets,
† variant commons) + starters from `blockdata/starters.txt`. Day-one moment:
you start with a starter deck purchase — historically what starting Magic WAS.

Modules (headless-first per the platform verdict; libGDX screens on top):

1. **Timeline service** — played-day tick, data-driven release calendar,
   normalized shelf windows (Alpha/Beta deliberately short = the first
   scarcity lesson), event feed hooks for the paper.
2. **Product/shelf service** — products per release, MSRP table (currency =
   period dollars; normalized prices, not historical fidelity), LGS daily
   stock roll (harvest Adventure `ShopData`/restock-reroll seeding).
3. **Collection service** — printing×finish inventory over forge-core
   `CardPool`/`PaperCard` (artIndex identity now; collector-number join
   arrives with the Scryfall import), per-set completion, new-card tracking.
4. **Pack ritual** — `BoosterGenerator`/`UnOpenedProduct` for collation; the
   reveal scene (seed: Adventure `RewardScene` flip; bar: Pocket's rip).
   THE quality-bar item and the only module with real unknowns.
5. **Buylist** — static sell prices; closes the dupes→currency→packs loop.
6. **Paper stub** — templated Chronicle issues: release announcements,
   last-chance shelf warnings, LGS stock notes, era flavor snippets.
7. **Persistence** — Adventure `SaveFileData` key-value pattern w/ migration
   shims from day one.
8. **Screens** — binder-first home, LGS/shelf, opening scene, paper overlay,
   settings (clock/knobs exposed per the ethics stance).

Candidate cheap rider: the **Ante pack-EV ledger stub** from day one (static
buylist prices make EV computable; the ethics identity ships with the MVP).

Stretch (kitchen table): deck editor wiring + ownership-legality only (no
format resolver needed — 1993–94 casual play predates formats; that resolver
arrives with the tournament board).

Open tuning items: daily ration size (2–3 packs?), MSRP/buylist number pass,
reveal-UX bar definition, dogfood exit criterion (proposal: the daily loop
still feels good after ~2 weeks of real use by the author).

## Circulation/market model v0 (2026-07-31, stage-2 design; user pins recorded)

User pins: **endpoint-backout adopted** (the only alternative is trusting
someone else's historical price records, which would have large holes);
**single global popularity curve** as the master demand driver, WITH custom
secondary multipliers for a small allowlist of famous cards — which is also
the mechanism for the **Reserved List as an in-game event** (a scripted event
that applies multipliers; alt-history prestige runs like "no Reserved List"
just drop the event); **exploit-resistance ranks ABOVE realism**, and
hand-tuning a small number of specific cards is acceptable in its service.

### State and supply

- Per printing: `printed` (normalized set print run × collation sheet weight),
  `opened` (monotone circulation), `price`. Everything else derives.
- **World-opening curve:** one logistic per set — slow at release (the world
  is slower than the player, per the round-2 pin), ramp through shelf life,
  long tail, **asymptote < 1**. `printed − opened` IS the sealed supply the
  trading sites sample from — out-of-print box offers are draws from a tracked
  quantity, not scripted content. (Alpha: tiny run, high asymptote → sealed
  Alpha late-game astronomically rare, matching reality unscripted.)
- Player openings add to `opened` directly: on recent sets the player is a
  genuine supplier (market-making/cornering emerge, not scripted).

### Prices

- **Endpoint-backout:** per printing, back out an intrinsic-desirability
  constant such that at full circulation + present-day demand the price lands
  on the (log-space-stretched) real Scryfall price by construction. Stretch is
  applied to endpoint targets BEFORE backout; all path arithmetic in stretched
  space. History then runs forward: early price = intrinsic × era demand ÷ era
  scarcity. Nobody hand-authors 100K price paths; famous cards end where they
  should.
- **Demand per tick (derived, not stored):** global popularity curve (Magic's
  player-base growth — makes "buy anything in 1994" long-run +EV and is the
  paper's most legible recurring story) × name-level playability (from
  backout, modulated by era events: bans, reprints, meta, later the
  gimmick-tournament rotation) × per-card override multipliers (the famous-
  card allowlist / Reserved List mechanism). Printings of one name are
  SUBSTITUTES: name demand allocates across printings inversely to supply,
  plus scarcity/age premiums — Beta > Unlimited falls out of arithmetic.
- Price relaxes toward target per tick (rate λ) + small seeded noise; shocks
  come from causes, never noise (standing principle).

### Player interaction and depth

- Listings = liquidity fraction of circulation, not all of it. Orders execute
  against depth: buying a large share of listings moves price superlinearly;
  cornering exhausts listings, then LEAKS — holders list more as price rises
  above their valuation (supply elasticity = corner-and-it-erodes for free).
  Selling adds listings and pushes down (the anti-chaff-dump brake).

### Anti-exploit invariants (rank above realism; pin before build)

1. **Buylist keys off a smoothed reference price** with spread widening under
   volatility — else buy-out-listings → spike → sell-to-buylist is an infinite
   money loop.
2. **Cracking packs is instant-EV-negative in currency terms by construction**
   (expected immediate buylist value of a pack < pack price, enforced in
   calibration) — profit comes from play, appreciation over time, and chase
   pulls, never from crack-arbitrage at scale. The Ante EV ledger displays
   exactly this, so the invariant doubles as the ethics feature.
3. Degeneracy review is a standing stage-2 gate: enumerate money loops
   (corner→buylist, stock-roll scumming, lot-resale chains) before tuning
   numbers; new mechanics must state their loop analysis.

### Calibration gate

Backout guarantees endpoints, not mid-path plausibility (real prices encode
real-world facts our fiction changes — normalized print runs absorb at the
endpoint only). Acceptance pass: eyeball generated paths for ~20 famous cards
(duals, Power, Necro, Jace-era staples) + the era gluts (FE, Chronicles crash
once the event fires). Compute is trivial: one arithmetic pass over
printings-in-existence per played day (~10² early, ~10⁵ endgame).

### MVP-adjacent note (from same session)

The MVP dogfood criterion (2 weeks of real daily use) implies **packaging the
playable branch for Android** — the fork builds forge-android upstream, but
our release pipeline is desktop-jar-only today; Android packaging joins the
MVP work implicitly and brings Android testing with it.

## Release-event structure & collectibility scope (2026-07-31)

User direction: include ALL the cards we can as available and collectible;
edge cases fold in as side-releases alongside a primary. Threshold question
partially punted — the two decisions below are the policy; per-product tier
assignment is a curated data file (one line per product) filled in era by era
as the calendar reaches it.

- **Three kinds, not two: events, riders, streams.**
  - *Primary release events* (one per played week, the calendar's unit):
    draftable expansions, core sets, and market-shock compilations (Chronicles,
    Modern Masters — anything whose story is a market event gets the
    headline).
  - *Side-releases (riders)*: precons/Commander decks, Duel Decks,
    Portal/Starter, promos, un-sets, oversized-format products (Vanguard/
    Planechase/Archenemy — real Forge play modes) — attached to a nearby
    primary: shelf space beside it, paper mention, fully collectible, no
    calendar slot. Deck products sell as sealed products (the product service
    is generic; Commander-deck-exclusive new cards enter through them).
  - *Continuous channels (streams)*: Secret Lair (~weekly from 2019) maps onto
    the trading-sites surface — direct-to-consumer in fiction and reality, a
    rotating drop stream riding whatever week it lands in.
- **Emergent deceleration:** cadence fixed at one primary/played week ⇒ era
  duration ∝ primary-product density — early years compress (~5 primaries in
  1994), modern years stretch (8–10). "Decelerate into the present" falls out
  of the normalization; no designed curve needed.
- **Scope pin: collectibility does NOT require Forge playability.** Un-cards,
  unscripted obscurities, oversized: binder-only with a not-engine-playable
  flag (the deckbuilder layer excludes them). Otherwise "include everything"
  silently shrinks to "everything Forge has scripted."
- **Excluded outright: digital-only printings** (Alchemy/Arena-only) — never
  cardboard; at most alt-history prestige material someday. Foreign-exclusive
  printings (FBB, Renaissance) ride the deferred language axis.

## Binder UX v0 — archaeology + design (2026-07-31)

Two sweeps run this session: a fork codebase dive (worktree `forge-play`) and
an upstream GitHub scan. **Upstream baseline: the field is clear** — nobody is
building a collection browser; zero pack-opening/reveal work (RewardScene
substantive changes all 2022–23). Watch items: PR #10636 (desktop deck-LIST
browser — conceptual neighbor, possible desktop-editor-structure collision if
merged), #11399/#11400 (small Adventure reward-overlay tweaks = future
RewardScene merge surface), #11093 (custom Scryfall-data API, still open,
relevant to the printing/price import). Repo now has stated UI guidelines
(#10637, merged May) — read before upstreaming any UI. **iOS support #11190
MERGED 07-24** — a libGDX binder now implicitly targets iOS too.

### What exists (key findings, paths in the fork)

- Adventure's editor SUBCLASSES the shared `FDeckEditor` (data-driven
  `DeckEditorConfig`, overridable pages, sanctioned `getColOverrides()` hook)
  — the extension pattern for a Chronicle screen is established, not invented.
- `ItemManager` grid (`ImageView`): group-by-SET exists (stats-free headers),
  pile-by-COLLECTOR_ORDER exists, pinch-zoom column count, persisted per-config
  prefs. `CardEdition.getObtainableCards()` carries collector number + rarity
  per set = the binder page spine. Quest has the ONLY completion math
  (`QuestUtilCards.getCompletionPercent`) — used solely for shop booster rows,
  never rendered as a grid.
- Reveal: TWO half-implementations — Adventure `RewardActor` (real 3D flip,
  sound, NEW/owned badges, rarity-ascending sort so the best card is LAST) and
  Planar Conquest `ConquestRewardDialog.CardRevealAnimation` (sequenced,
  skippable, FScreen-native). Neither does flip + sequencing together;
  combining them = the reveal scene. Desktop has no reveal at all.
- Affordances present: favorites/stars (grid-rendered), NEW column (list-view
  text suffix ONLY), Adventure `newCards`/`favoriteCards`/`autoSellCards`
  persisted in saves, foil rendering (`Graphics.drawFoil`, pref-gated),
  grayscale shader (`RewardActor` :1177) = ready-made unowned-slot look.

### The four gaps (all small)

1. **NEW badge never renders in the image grid** (~10-line plumb via the
   existing `fnIsFavorite`/`fnPrice` pattern in `ImageView.setup`/`ItemInfo.draw`).
2. **Nothing renders unowned cards** — pool == owned everywhere. Binder needs
   pool = full set, owned-count as decoration (overridable
   `CatalogPage.getCardPool` makes this per-page, no ItemManager surgery).
3. **Group headers carry no completion stats** — one `g.drawText` site;
   denominator = generalize Quest's completion helper onto
   `CardEdition.getObtainableCards()`.
4. **No per-set symbol assets** — only rarity sprites + per-set BOOSTER ART
   (`ImageKeys.BOOSTER_PREFIX`). Proposal: shelf tiles wear booster/box art
   (charming, zero new assets); Keyrune (OFL font) later if real symbols wanted.

### Design shape v0

- **Two levels: shelf → spread.** Shelf = custom simple screen, one tile per
  binder/set (booster-art cover, completion bar, NEW-count pip), release
  order. Spread = ImageView-derived grid: full-set pool in collector-number
  order, unowned = grayscale silhouette (the gap IS the motivation), owned =
  art w/ qty pip, NEW glint until viewed. New `ItemManagerConfig.BINDER_*`
  entry + column factory; group/pile/persistence come free.
- **New-card lifecycle upgraded:** Adventure clears `newCards` wholesale on
  editor close; binder wants per-card clear-on-seen (viewed in spread) + per-
  set rollup on the shelf. Persisted, timestamps optional.
- **Completion headline = one-of** (pinned earlier): playset a deckbuilder
  stat, master (× finish/variant) the per-set endgame toggle.
- **Reveal scene = RewardActor flip × Conquest sequencing** + rarity-tiered
  staging (best-last sort already exists). MVP window has no foils ⇒ the foil
  shimmer moment debuts WITH the 1999 event — the UX and the timeline agree.
- **Performance:** ImageCache LRU (120 textures, 1 new image/frame streaming)
  + non-virtualized ItemInfo = fine for the MVP window (sets ≤ 295 cards);
  modern-era 300+ sets stream slowly — placeholder-first draw + (later)
  virtualization flagged, NOT MVP work. Full-collection views stay
  list/search-based; the binder is always per-set-bounded.

Aesthetic forks CLOSED (2026-07-31, user): **continuous scroll with
grayed-out missing cards is the original view** — physical binder covers/pages
are fun but not first-layer (they return as cosmetics, below). Completion
rewards deferred from MVP but scoped now (next section).

### Cosmetics & completion rewards — scoped, deferred (2026-07-31)

Not built at first; option space recorded so the completion bars have
somewhere to point later. Pocket's roster: coins, playmats, sleeves,
backdrops, binder covers, avatars + non-displayable achievement trophies.
Two organizing cuts:

- **By asset cost.** Tier A, zero new art: binder covers from existing
  booster/box art, trophies as framed card art, avatars (Forge already ships
  avatar sprite sets), sleeve patterns from card backs — note upstream desktop
  already has a deck-sleeves feature to harvest. Tier B, low/procedural:
  frame/border styles, color themes, shelf backdrops, foil-shimmer binder
  treatments. Tier C, original artwork: playmats, display boards, dioramas,
  playmat toys — expensive, later/maybe.
- **By surface: binder-side vs table-side.** Binder-side cosmetics (covers,
  sleeves-as-displayed-in-binder, trophies, shelf backdrop) decorate the
  surface the MVP actually has — they come first. Table-side cosmetics
  (playmats, dice, counters, toys) decorate play surfaces that don't exist
  until the kitchen-table/battler layers — they wait by construction.
- **MTG-native substitution:** Pocket's coins are load-bearing because Pokémon
  flips constantly; MTG's equivalent daily-handled objects are DICE and
  counters (spindowns, d20s, token/counter cosmetics) — the right analog when
  table-side cosmetics arrive.
- **3D ambitions (far-stretch, recorded as aspiration):** tactile 3D pack
  openings, a 3D play mode in the modern-digital-TCG style with rendered
  counters/playmat toys, 3D display dioramas. All gated on original-art
  budget the project doesn't have; sights deliberately set lower at first —
  the existing flip + sequenced-reveal machinery gets most of the tactile
  feel in 2.5D.

### Awards round 2 (2026-07-31 session 3 — first-pass picks + sourcing principles)

- **Standing art-sourcing principle (user + session): reuse-first, then
  derive-from-card-art the way Forge itself does** (user notes existing player
  icons are cropped cards — verify the specific claim at build time; the
  pattern is real regardless). Corollary adopted: **derive cosmetics at
  RUNTIME from the card images Forge already downloads** (crops, tiles,
  shader treatments) — never ship baked derived assets. Keeps the repo free
  of new-provenance art and makes the upstream story identical to Forge's
  existing one. **Generated art (ComfyUI) = fork-only experimentation at
  most** (user flags it as less popular for upstreaming — agreed); upscaled
  *real* card art sits closer to existing practice but any upscale step also
  stays runtime/user-side, not committed to the repo.
- **Aesthetic north star noted, decision deferred (user):** purposeful-retro
  pixel/PS1 chrome in the modern deliberate style (reference: Queen's
  Domain), not literal old design. Period argument: a 1993–94 mode rendered
  like era software (the Shandalar generation — hi-res card scans inside
  lo-fi chrome) extends the period-authenticity principle to the UI itself;
  in-repo precedent: Adventure's overworld is already pixel art. Strategic
  note: committing to deliberate lo-fi **collapses cosmetics Tier C into
  Tier B** (backdrops/display cases/playmat toys become solo-dev-producible)
  — the aesthetic call is secretly a cosmetics-budget call.
- **First award pass = avatars (user pin):** scale Forge's crop derivation —
  set completion unlocks avatars cropped from that set's legends/characters.
  MVP has no match surface, so the avatar's home is a collector-profile
  corner on the binder home / the paper byline.
- **New roster item, adopted as the cheapest and most on-brand: paper
  write-up awards.** Completion achievements arrive as *Chronicle clippings*
  ("Local collector completes Antiquities!"); the trophy room is a
  **scrapbook of clippings** (text + card thumbnails, zero art); masthead
  titles as prestige labels. Nothing else is this cheap or this un-copyable.
- **Easy-shelf sequencing:** binder-side + MVP-era-displayable: clippings,
  binder covers (booster/box art per-set completion), avatars,
  framed-card/framed-wrapper trophies, foil-shimmer treatments (gated behind
  1999 with everything foil). Table-side, wait for play surfaces by
  construction: sleeves (harvest desktop deck-sleeves; card backs + art
  crops), **battlefield backgrounds from basic-land art (user idea, adopted
  — abundant, period-spanning; archaeology-check where the match screen
  draws its background before pricing)**. Ride the aesthetic call:
  procedural frames/borders/color themes, shelf backdrop progression (milk
  crate → shelf → glass case — the incremental-genre visual).

## Upstream strategy (2026-07-31, user decision): fork-first, re-cut later

The maintainers are conservative and favor small, lightweight PRs. Two ways to
build a whole mode against that: (a) plan in upstream-sized steps from the
start and submit one at a time, or (b) build freely on the fork, then cut the
result into synthetic, individually-reviewable commits with trimmed test
suites when upstreaming. **Decision: (b), fork-first.** More duplicated work,
but cleaner results with less delay and politics — and the project has direct
evidence the re-cut workflow works (multiplayer hardening: private-branch
work re-cut onto clean upstream master, 3 advisories merged byte-identical;
PR #11203 re-authored the same way; report 1's 14-file→2-file re-cut was
taken whole).

Riders on the decision:

- **Isolation convention keeps the rebase tax ≈ 0:** Chronicle code lives in
  its own packages (Adventure precedent: a whole directory + a handful of
  shared-file hook lines). New-mode code is additive by construction; the
  playable branch's periodic upstream merges stay conflict-free, and the
  eventual re-cut is mostly "lift the directory."
- **Carve-out — the standalone prosocial tracks stay upstream-first-friendly:**
  the Scryfall printing/multilingual import (coordinate with open PR #11093,
  not against it), Android asset delta updates, and era rulesets (Premodern /
  Old School constituency) were always framed as independent contributions
  and can go upstream on their own schedule regardless of Chronicle.
- **The "float in Discord before writing code" risk note is softened:**
  under fork-first the concept float is goodwill and timing, not a gate — we
  don't need permission to build on our own fork, and the playable branch is
  already a live distribution channel to real users (friends' auto-updating
  installs) independent of upstream acceptance.

## Implementation planning round (2026-07-31 session 3 — promotion; pins recorded)

Chronicle scheduled ([ADR-0029](../decisions/ADR-0029-chronicle-scheduling.md));
staging and architecture live in [chronicle-mvp-plan.md](chronicle-mvp-plan.md).
Design-record deltas from the session:

- **"Streaming" clarified = upstreaming.** The long-range goal is Chronicle as
  an upstream Forge mode; the fork-first/re-cut strategy (previous section) is
  the vehicle. No architectural addition — but it hardens the Quest-precedent
  placement, desktop-tree tests, and UI-guidelines adherence chosen in the plan.
- **MVP income gap found and closed: allowance stipend.** The MVP as previously
  specced had no income source (battler out; pack-cracking instant-EV-negative
  by invariant; buylist only recycles) — currency strictly drained and the LGS
  was unreachable. Fix (user): a small cash allowance on the played-day
  schedule (lean weekly lump; dogfood decides), kitchen-table-kid period
  flavor, retiring/reflavoring when tournament income arrives in stage 3.
- **Day-tick semantics formalized** (derived from the played-day pin): the tick
  fires on **ration collection**, not app launch; at most one per real calendar
  day (local time, ~4am grace); all daily channels key off the current day
  index; pre-collection the player is still living the previous in-game day.
- **Seed-integrity invariant adopted** (corollary of
  exploit-resistance-above-realism): all daily randomness deterministic from
  (run seed, day index, domain); **sealed items commit contents at
  acquisition**, reveal at opening — restart/reload can never reroll a pull or
  stock roll. Also pre-builds stage 2's sealed-supply property.
- **Prestige-proof schema from day one:** run-id on the collection layer +
  separate meta-progress blob (prestige = "collection resets, meta persists"
  is a schema property; free now, painful later).
- **Visibility (user): hidden until the dogfood gate passes** — pref-gated menu
  entry; friends meet Chronicle when the daily loop is proven. Android
  packaging spike runs parallel-early; Discord courtesy float timed at the
  visibility flip.

### Reveal-UX bar v1 (same session, user pins — the D3 open item CLOSED)

The bar decomposes into identity × mechanical tier × scale contract; all four
pins took the recommended option:

- **Identity: period wrapper, evolving with the timeline.** The reveal object
  is the set's REAL booster art (`ImageKeys.BOOSTER_PREFIX` — already shipped
  per set, zero new assets); treatment evolves as history does — plain '93–94
  wrappers, foil-era gloss debuting with the 1999 event (the third instance of
  the UX-and-timeline-agree pattern), modern treatments late. Borrows Pocket's
  *interaction grammar* (rip gesture, tap pacing) while rejecting its neon
  aesthetic — an identity no commercial gacha can copy, because their history
  is fake.
- **Mechanical tier for MVP: tier 2** — player-paced: rip/drag gesture on the
  wrapper to open, tap-to-flip (anticipation under the player's thumb — argued
  to be the real core of Pocket's feel, more than particles), commons
  batch-flip fast, rare-slot buildup (delay/glow/sting), NEW glint. Tier 3
  (tear physics, particle language, original audio identity) = post-dogfood
  polish, not MVP. *(Amended later same session, user: **no 3D pack at first**
  — but the wrapper open is a REAL animated motion, a tear you watch driven by
  the drag, not a static wrapper cutting to cards. 2.5D throughout; the 3D
  ambitions stay far-stretch as recorded.)*
- **Scale contract: BOTH registers ship day one.** Planning found the sketch's
  "bulk UX is late-game" placement wrong by one day: the day-one moment is a
  60-card starter, and the MVP LGS sells 36-pack boxes. So MVP ships the
  single-pack full ceremony AND a batch mode — the bulk-lot design's machine
  (rapid scroll, auto-pause on rare/NEW/value) with different pause rules —
  player-switchable. Starters/boxes route through batch by default.
- **Sound/haptics: harvest + tiny pass.** Existing Forge/Adventure audio,
  libGDX vibrate on mobile, and a couple of sourced CC0 sounds permitted
  (wrapper rip, card flip, rare sting) where the harvest lacks them.
- Standing properties: player-paced, always skippable, never value-gating (the
  ethics stance applied to the reveal); best-last staging (Adventure's
  rarity-ascending sort); mouse parity (tap=click, rip=drag) since dogfood
  starts on desktop.
- **The bar statement** (D3's done-when): *the 200th single-pack opening still
  produces a beat of anticipation before the last card; side-by-side with
  Pocket reference footage the ritual isn't embarrassing; a box/starter batch
  reveal preserves the jackpot moment in ~a minute.*

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

**Reordered 2026-07-31 (daily-gacha-v1 session): the vertical slice is the
collector loop, not the battler.** New order: (1) MVP slice — timeline service +
normalized release calendar + in-print shelf + pack ritual (era collation via
forge-core) + binder + paper stub; (2) circulation/market model (slow singles,
LGS stock roll, trading-site offers, bulk lots); (3) battler + tournament board
(the old item 1 folds in here); remaining items keep their relative order below.

1. ~~**Idle battler spike:** harness → Quest inventory → credits formula. Heuristic AI
   only, no UI beyond numbers. Proves the loop.~~ *(Demoted to stage 3 — see
   reorder note above; still the cheapest proof of the battler layer when its
   turn comes.)*
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
