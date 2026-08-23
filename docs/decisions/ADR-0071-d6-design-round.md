# ADR-0071: Chronicle D6 design — rival collectors, a cash purse, borrowed decks

- **Date:** 2026-08-22
- **Status:** accepted
- **Design-doc anchor:** [ADR-0070](ADR-0070-chronicle-effort-reward-sink.md)
  (which opened these questions);
  [chronicle-mvp-plan.md](../design/chronicle-mvp-plan.md) D6;
  [collection-mode-sketch.md](../design/collection-mode-sketch.md) layers 1–3

## Context

ADR-0070 promoted the kitchen-table stretch to deliverable D6 and left three
questions open: the purse's flavor, how deck legality reads the collection, and
the economy knock-on. This ADR settles them, plus the two the build immediately
forced — who the opponent is, and where its deck comes from.

**Fork archaeology done first; D6 needs no new machinery.** Every piece exists:

- `DeckGeneratorBase(IDeckGenPool, DeckFormat)` (`forge-core`) takes an
  **arbitrary** pool of `PaperCard`, with mono/2/3/4/5-colour subclasses, a
  CMC-curve pass (`addCmcAdjusted`), creature/spell split, basic-land
  percentage, and a `forAi` flag. Chronicle's collection is already a `CardPool`
  over `PaperCard`, so "build a deck from exactly these cards" is a constructor
  call. It is a curve-and-colour heuristic, not archetype-aware — pool-agnosticism
  is the property that matters.
- `FDeckEditor.DeckEditorConfig` already carries the two hooks a
  collection-restricted editor needs: `getCardPool()` and
  `usePlayerInventory()`. The latter is Quest's existing concept and already
  means what we want (see the legality decision below).
- `MatchController.hostMatch()` + `hostedMatch.startMatch(rules, variants,
  players, guiMap, playlist)`; `forge.adventure.scene.DuelScene` is the harvest
  template, the same way Chronicle harvested Adventure's `ShopData` and
  `SaveFileData`.

**Finding of record: there is no corpus of period decklists, and that is
historically correct.** 1993–94 predates published deck tech; the earliest
well-documented lists (Zak Dolan's 1994 Worlds deck, Weissman's "The Deck")
post-date the MVP window's close at Fallen Empires. The three shipped Forge
deck corpora are all anachronistic for the window: the LDA archetype models
(`res/deckgendecks/*.lda.dat`) cover Modern/Legacy/Historic/Pauper only, and
Legacy's archetypes are Sneak Show and Merfolk; the 505 quest precons are real
WotC preconstructed decks, nearly all modern; the 786 `geneticaidecks` are
GA-evolved Legacy lists. Nothing to import, and importing would be wrong.

## Decision

1. **The purse is cash by default; ante is an opt-in stake with a better
   payout.** Ante is period-authentic and is what the Ante module is named for,
   but as the *default* it inverts the mode's core loop: everything in Chronicle
   is accumulation (binder filling, NEW badges, first-pull glints, completion
   bars), and ante makes the primary reward channel **subtractive from the
   collection** — a loss does not merely fail to reward, it undoes earlier
   sessions. That reads far worse in a collection game than in a combat game,
   and the seed-integrity invariant sharpens it: an ante loss is permanent and
   unrerollable by construction. Offering ante as a *choice* is both the
   period-accurate framing (playing for ante was a decision people made, not the
   default) and gives effort→reward a **risk** dimension on top of its time
   dimension.

2. **The opponent is a small cast of named rival collectors, each with its own
   seeded collection that grows along the same timeline the player walks.** The
   rival's deck is generated from *that rival's pool*, not from the global card
   list. Consequences that make this the right shape rather than just the
   flavourful one:
   - **Difficulty rises with the era for free, in fiction.** A rival can only
     play what has been released, so the power curve is the timeline's, not a
     knob we have to tune.
   - **It gives the paper someone to write about** — `ChroniclePaper` currently
     templates releases, shelf warnings and stock notes; rivals are the first
     content with a narrative arc. A rival who opens a Lotus is a headline.
   - **The period-correct opponent genuinely is another kitchen-table player
     with a jank collection**, which is exactly what pool-restricted generation
     produces, weaknesses included.
   - **Seed integrity extends to rivals unchanged:** a rival's acquisitions
     derive from (run seed, rival id, day index) like every other daily channel,
     so their collection is not rerollable either.

3. **Deck legality is reference-only: decks borrow, they do not consume.** A
   deck names owned copies; building one does not remove them from the binder,
   and two decks may name the same card. Per-deck copy limits still apply (you
   cannot run 5 Bolts on 3 owned). This is exactly what
   `DeckEditorConfig.usePlayerInventory()` already means in Quest, so it is the
   default behaviour of machinery we are already reusing rather than something
   to build. It also matches how a kitchen-table player actually behaves — a
   card moves between decks between games. Reservation semantics were
   considered and rejected for now: they would make duplicates meaningfully
   valuable (which the buylist currently lacks any tension around) but need
   reservation state in the save schema and a UI to explain it, and that trade
   is not worth taking before the loop is proven.

4. **Deck generation is `DeckGeneratorBase` over a `DeckGenPool` built from the
   relevant collection**, for both the rival and the player's optional
   auto-build. Period `.thm` archetype files (the `res/quest/themes/` format —
   `BasicLandPercentage` plus percentage-weighted card groups) are an **optional
   later layer**, not D6 scope: hand-authoring Weenie White / Land Destruction /
   Big Green / Counterburn fits the mode's curated-data-file convention and
   would sharpen rival identity, but it is per-era data work rather than
   something that scales with the timeline on its own.

5. **Anvil is the designed long-run replacement, behind the same interface.**
   The sketch already plans this as layer 3's "deck judge = sim probe," with
   Tutor's learned scorer replacing it. D6 should therefore put rival-deck
   construction behind a narrow seam (pool in, deck out) so the generator can be
   swapped without touching the rival, purse or match code. Explicitly **not**
   D6 work — noted so the seam exists when it is.

## Consequences

- **The grind question is now the live one, and it is where pin 8 gets tested.**
  Unbounded paying rematches would be an income exploit (anti-exploit invariants
  rank above realism) and would sit badly with the mode's no-engagement-traps
  ethics stance, under which the player owns their clock. But a hard daily cap
  partly defeats pin 8's "put more time in, get more out."
  **Recommended shape, to be confirmed by dogfood rather than pinned here:**
  each rival offers **one paying challenge per in-game day**; rematches are
  always playable and always free but pay nothing; the purse **scales with the
  rival's difficulty**; and the rival cast **grows with the timeline**. Time then
  converts into progress through *deck quality and taking on harder rivals*
  rather than through repetition, and daily earning capacity grows with the era
  on the same curve as everything else. If dogfood reads this as still too
  bounded to satisfy pin 8, the pin stands and the shape changes — that is what
  pin 8 being above the stage line means.
- **The numbers pass (D5) stays deferred and now has a second axis**: purse
  size per difficulty tier, and the ante multiplier. Total inflow was a fixed
  weekly constant; it is now variable in both amount and cadence.
- **The Ante ledger gets its first honest use.** It currently accounts
  pack EV only; an opt-in ante stake is literally what the module was named
  for, and the ledger should account it from the first commit.
- **`ChroniclePaper` gains a content source** — rival results and rival
  acquisitions are event-feed material. Not required for D6 to land, but the
  hooks exist and it is cheap.
- **Save schema grows** by the rival cast (ids, seeded collections or the seeds
  to regenerate them, per-day challenge state) and the player's decks. Both
  belong on the run layer, not the meta layer, per the prestige-proof split
  (plan pin 7).
- **Open, deferred to build time:** how many rivals and how fast the cast grows;
  whether a rival's pool is stored or regenerated from seed on load (the latter
  is cheaper and matches the seed-integrity posture, but costs determinism if
  the generator ever changes — a versioned generator, or storing the pool, will
  be needed).
