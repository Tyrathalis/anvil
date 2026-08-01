# Chronicle MVP — implementation plan v1

- **Date:** 2026-07-31 (planning session 3; promotion recorded in
  [ADR-0029](../decisions/ADR-0029-chronicle-scheduling.md))
- **Status:** active
- **Design record:** [collection-mode-sketch.md](collection-mode-sketch.md) stays
  canonical for all design content; this doc owns *implementation* — architecture,
  staging, gates. Design changes still go into the sketch (or an ADR), never here.
- **Stream identity:** a playable-branch side stream, sibling to the QoL/fork work —
  NOT on the M4 research path. M4 owns the research hours; Chronicle competes for the
  playable-fork budget.

## Scope

Exactly the MVP slice spec v0 (sketch, 2026-07-31): content window 1993–94
Alpha→Fallen Empires (9 booster releases + starters), thin economy (static
era-flat buylist + LGS + seeded daily stock roll), identity = printing×finish
(language dormant, condition never), kitchen-table play = stretch. Foils,
battler, tournaments, market/circulation, trading sites, bulk lots, trade
night, puzzles, prestige, languages: OUT.

## New pins from this session (user, 2026-07-31)

1. **"Streaming" was a typo for upstreaming.** Chronicle-as-upstream-mode is the
   long-range goal; the already-pinned fork-first/re-cut strategy is the vehicle.
   No separate architecture — but it hardens the placement/test/UI-guideline
   choices below, all picked to keep the eventual re-cut cheap.
2. **MVP income = allowance stipend.** Small cash on the played-day schedule
   (lean: weekly lump — creates save-up-for-a-box decisions; dogfood may demote
   to daily), period-perfect kitchen-table flavor. Exists because the MVP has no
   income engine (battler out, pack-cracking instant-EV-negative by invariant):
   without it, currency strictly drains and the LGS is unreachable. Retires or
   reflavors when tournament income arrives in stage 3.
3. **Android packaging spike runs parallel-early** (D4 below), not first and not
   deferred; desktop via `forge-gui-mobile-dev` covers early dogfooding.
4. **Hidden until dogfood passes.** Menu entry pref-gated, default off, until the
   author's two-week gate clears; friends meet Chronicle when the daily loop is
   proven. First impressions are disproportionately expensive for a collection
   mode.
5. **Day-tick semantics formalized** (derived from the "a day you open your packs
   is an in-game day" pin): the tick fires on **ration collection** — the
   consuming act — never on app launch; at most one tick per real calendar day
   (local time, with an early-morning grace window ~4am so the midnight opener
   isn't cheated); all daily channels (LGS stock roll, future trading-site
   offers) key off the current day index; before collecting, the player is still
   living the previous in-game day (binder browsing and yesterday's stock remain
   available — harmless, since stock is deterministic per day and already seen).
6. **Seed-integrity invariant** (corollary of exploit-resistance-above-realism):
   all daily randomness derives deterministically from (run seed, day index,
   domain); **sealed items commit their contents-seed at acquisition** and reveal
   at opening. Quit-without-saving can never reroll a pull or a stock roll. This
   also pre-builds the stage-2 property that out-of-print sealed boxes are
   draws from tracked supply with committed contents.
7. **Prestige-proof save schema from day one:** run-id on the collection layer +
   a separate meta-progress blob. Prestige ("collection resets, meta persists")
   is far out, but it's a schema property — free now, painful to retrofit.

## Architecture decisions

- **Placement (the isolation convention, concretized):**
  - Headless services: `forge-gui/src/main/java/forge/gamemodes/chronicle/`
    (the Quest precedent — toolkit-agnostic by module structure: `forge-gui`
    cannot see the mobile toolkit at compile time, so headlessness is enforced
    structurally, not by discipline).
  - Screens: `forge-gui-mobile/src/forge/chronicle/` (libGDX frontend per the
    platform verdict; runs on desktop via `forge-gui-mobile-dev`, on Android,
    and — since #11190 merged — implicitly iOS).
  - Data: `forge-gui/res/chronicle/` (release calendar, MSRP/buylist tables,
    paper templates).
  - Entanglement budget: hook lines in shared files kept to a handful
    (menu entry, save-dir registration) — Adventure's precedent, and what keeps
    both the periodic upstream merges and the eventual re-cut ≈ free.
- **Tests:** TestNG in `forge-gui-desktop`'s existing tree (the
  RotatedRect/DeckSiteSync precedent; mobile has zero test infra and gets none).
  The headless core makes this natural — timeline, shelf windows, collation
  counts, buylist math, stipend, save round-trips all test without a display.
- **Persistence:** Adventure `SaveFileData` key-value pattern with migration
  shims from the first commit; own directory; save slots; run-id + meta split
  per pin 7.
- **Release calendar = a curated data file**, one row per product: order index,
  edition code, kind (primary/rider/stream — riders and streams unused in the
  MVP window but the field exists), shelf-window override, MSRP, ration
  eligibility. Seeded with the 9 MVP products (Alpha, Beta, Unlimited, Arabian
  Nights, Antiquities, Revised, Legends, The Dark, Fallen Empires) + starters.
  This file is the artifact the "curate the master release list" task grows,
  era by era.
- **Currency:** period dollars, integer cents.
- **Upstream posture:** fork-first per the sketch's strategy section; read the
  merged UI guidelines (#10637) before building screens; the courtesy Discord
  concept-float is best timed around the visibility flip (D5 exit), when there
  is something real to show.

## Deliverables

**D0 — promotion paperwork.** This doc + ADR-0029 + sketch header/status
updates. Done with the commit that lands this file.

**D1 — headless core.** Package skeleton + timeline service (played-day tick
per pin 5, release calendar, shelf windows incl. the deliberately-short
Alpha/Beta scarcity lesson, event-feed hooks), product/shelf service (MSRP,
LGS daily stock roll — harvest Adventure `ShopData`/restock-reroll seeding,
re-keyed to pin 6 determinism), collection service (printing×finish over
forge-core `CardPool`/`PaperCard`, artIndex identity now, per-set completion,
new-card tracking with per-card clear-on-seen), buylist + stipend, pack
generation via `BoosterGenerator`/`UnOpenedProduct` behind the sealed-item
seed commitment, persistence. Rider: the **Ante pack-EV ledger stub** (static
prices make EV computable; the ethics identity ships with the MVP).
*Done-when:* a **simulated-fortnight test** — 14 scripted played days
exercising ticks, a release event, shelf turnover (Alpha leaving the shelf),
rations, LGS purchases, buylist sales, stipend credit, and a mid-fortnight
save/reload with identical continuation — green in the desktop test tree,
alongside unit tests per service.

**D2 — screens v1.** Binder shelf→spread (closing the four archaeology gaps:
NEW-badge plumb to the image grid, unowned-card rendering via per-page
`getCardPool` override + grayscale shader, completion stats in group headers,
booster-art shelf tiles), LGS/shelf screen, paper overlay (templated issues),
settings (clock/knobs per the ethics stance), pref-gated home-menu entry
(default hidden, pin 4). *Done-when:* the full daily session script is
playable start-to-finish on desktop via `forge-gui-mobile-dev`.

**D3 — the reveal scene.** Bar DEFINED (sketch, "Reveal-UX bar v1" — all four
pins user-taken 2026-07-31): **period-wrapper identity evolving with the
timeline** (the reveal object is the set's real booster art via
`ImageKeys.BOOSTER_PREFIX`; foil-era gloss debuts with the 1999 event; Pocket's
interaction grammar without its aesthetic), **tier 2 mechanics** (rip/drag to
open, tap-to-flip player pacing, commons batch-flip, rare-slot buildup, NEW
glint; tier-3 polish = post-dogfood), **both registers day one** — single-pack
ceremony + batch mode (rapid scroll, auto-pause on rare/NEW/value) because the
day-one starter is 60 cards and the MVP LGS sells boxes; starters/boxes route
through batch by default — and **harvest + tiny sound pass** (existing audio,
libGDX haptics, a few CC0 sources permitted). Machinery: `RewardActor` 3D flip
× `ConquestRewardDialog` sequencing + best-last staging. Gather Pocket
reference footage at build time for the side-by-side. *Done-when (the bar
statement):* the 200th single-pack opening still produces a beat of
anticipation before the last card; side-by-side with Pocket footage the ritual
isn't embarrassing; a box/starter batch reveal preserves the jackpot moment in
~a minute. Expect iteration through D5.

**D4 — Android packaging spike** (parallel, any time from D1 on). Build
`forge-android` from the `playable` branch, sideload the APK, boot Chronicle
on-device. Explicitly out: Android update delivery — manual sideload is fine
for a two-week dogfood; delta updates on Android fold into the already-queued
prosocial track. *Done-when:* the daily loop runs on the phone.

**D5 — dogfood + numbers.** Two weeks of real daily use by the author (on the
phone, per the design's mobile-first lean), plus the tuning pass: ration size
(2–3 packs?), MSRP/buylist/stipend table, allowance cadence (weekly lump vs
daily). *Exit criterion:* the daily loop still feels good after ~2 weeks — then
flip the visibility pref for friends (beta), and take the courtesy Discord
float. A failed exit is design feedback for the sketch, not a death sentence.

**Stretch — kitchen table.** Deck editor wiring + ownership-legality only
(1993–94 casual play predates formats; the format resolver arrives with the
tournament board). Build only if the slice lands early.

## Open items (tracked, not blocking)

- ~~Reveal-UX bar definition~~ CLOSED 2026-07-31 (sketch "Reveal-UX bar v1";
  D3 above carries the operative form). Residue: gather Pocket reference
  footage at D3 build time.
- Numbers pass: ration size, MSRP/buylist/stipend, allowance cadence (D5).
- Stage-2+ design threads unchanged in the sketch: implementable market spec,
  famous-card multiplier allowlist, per-product tier data file, completion-award
  selection from the cosmetics tiers.

## Risks

- **The reveal scene is the quality bar** — the one module where "buildable as
  written" doesn't apply. Mitigated by sequencing it after the loop exists (D3)
  so iteration happens against a playable game.
- **forge-android pipeline unknowns** — upstream builds it, our release
  pipeline is desktop-jar-only. The parallel-early spike (D4) retires this well
  before the gate needs it.
- **Hours competition with M4** — the standing risk, unchanged; the stages
  above are independently shippable chunks per the sketch's mitigation.
