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
buylist — rarity/era-flat + the 1994-desirability tier table — + LGS + seeded
daily stock roll), identity = printing×finish
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

**D1 — headless core. DONE 2026-07-31 (fork `playable` @ `574abedc08`): all
modules built, done-when gate GREEN** — simulated fortnight + 27 service unit
tests (30 total) in the desktop tree; full desktop suite 400 green;
shared-file footprint 3 additive `ForgeConstants` lines. Records: devlog
2026-07-31-session4. Addendum to pin 5 (found by the gate suite): the tick
guard is *strictly monotonic* on the effective calendar day — an equality
check would let a wound-back device clock re-arm the tick; seeds protected
pulls from savescum, the tick needed its own monotonicity against clock-scum.
Implementation notes: boxes materialize at purchase as component boosters,
each with its own committed seed (box-as-item deferred to stage 2, which the
acquisition-commitment property already serves); `BoosterSlot.replaceSlot()`
uses raw `Math.random()` — irrelevant in-window, must be fixed upstream
before any post-2018 content window; notables are priced by NAME only (ATQ
prints the same name at split rarities). Original spec:
Package skeleton + timeline service (played-day tick
per pin 5, release calendar, shelf windows incl. the deliberately-short
Alpha/Beta scarcity lesson, event-feed hooks), product/shelf service (MSRP,
LGS daily stock roll — harvest Adventure `ShopData`/restock-reroll seeding,
re-keyed to pin 6 determinism), collection service (printing×finish over
forge-core `CardPool`/`PaperCard`, artIndex identity now, per-set completion,
new-card tracking with per-card clear-on-seen), buylist + stipend (buylist =
rarity/era-flat PLUS the hand-authored **1994-desirability tier table** — the
famous-card allowlist file's MVP-window column, still fully static; sketch
"Famous-card allowlist v0"), pack
generation via `BoosterGenerator`/`UnOpenedProduct` behind the sealed-item
seed commitment, persistence. Rider: the **Ante pack-EV ledger stub** (static
prices make EV computable; the ethics identity ships with the MVP).
*Done-when:* a **simulated-fortnight test** — 14 scripted played days
exercising ticks, a release event, shelf turnover (Alpha leaving the shelf),
rations, LGS purchases, buylist sales, stipend credit, and a mid-fortnight
save/reload with identical continuation — green in the desktop test tree,
alongside unit tests per service.

**D2 — screens v1. DONE — gate PASSED 2026-08-01 (author's interactive pass:
begin/paper/allowance/opening/binder all work); built at `bb7e670cff`,
feedback round 1 at `59adfb8707`.** Feedback round landed same day:
**ChronicleAcquisitionLog** (provenance journal — every opening recorded w/
per-card first-pull ordinals, persisted; `sourcesFor` = which products yield a
printing), binder "Sort: New" = true acquisition order, deals section above
the shelf, reveal long-press → match-inspect CardZoom (oracle flip), pack
images prefetch at open. **Backlog from the pass:** ~~provenance UI~~ BUILT 2026-08-01
(`fedfea5126`: context menu on the spread grid — owned card → opening
history with first-pull ordinal + day/product per opening + xN duplicate
counts, pre-journal acquisitions degrade gracefully; any card → where to
find via `sourcesFor` + in-print/not-yet-released/out-of-print for today;
new `copiesIn` log helper, test-covered, suite 35 green),
desktop scroll-bar indicator on FScrollPane grids, stronger art preloading
(~~block/preload before the D3 reveal scene starts~~ folded into D3), save-slot browser
(currently one implicit run: autosave.sav, loaded automatically on entry —
multiple runs = the slot UI + ChronicleSaveIO's already-built slot files).
**Fidelity answers recorded:** 15-card ABU boosters accurate; no basics in
boosters = Forge's era-sheet model (historically ABU commons sheets DID carry
basics — documented deviation, engine-wide to change, not Chronicle-local);
random 5-color starters = period-accurate (1993-94 starters were random
assortments, not preconstructed); collector-number order = the canonical set
order (retroactive for pre-Exodus sets: WotC's color-then-alphabetical
convention, which our resolver follows). Original spec: All four binder archaeology gaps closed (NEW badge + unowned rendering
+ owned pips via generic NEW/OWNED ItemManager column-override plumbs in the
image view — upstreamable; completion stats via a group-caption composer hook;
booster-art shelf tiles). Home/LGS/paper/settings + pref-gated New Game entry
(CHRONICLE_MODE_ENABLED, default off; flip in Settings→General) shipped; the
opener is a deliberate tap-through placeholder for D3. Notes: unowned cards
grayscale when the image is on disk, dimmed composed placeholder otherwise (no
network fetch for unowned); per-cell grayscale flushes the sprite batch —
batching optimization deferred until a device shows it matters (D4 spike);
`markSeen` flushes on spread exit, one autosave per batch. Original spec:
Binder shelf→spread (closing the four archaeology gaps:
NEW-badge plumb to the image grid, unowned-card rendering via per-page
`getCardPool` override + grayscale shader, completion stats in group headers,
booster-art shelf tiles), LGS/shelf screen, paper overlay (templated issues),
settings (clock/knobs per the ethics stance), pref-gated home-menu entry
(default hidden, pin 4). *Done-when:* the full daily session script is
playable start-to-finish on desktop via `forge-gui-mobile-dev`.

**D3 — the reveal scene. v1 BUILT 2026-08-01 (fork `playable` @ `8c2134fdbf`):
both registers shipped** — ceremony (drag-to-tear wrapper with the set's real
booster art + shearing strip fly-off, tap-to-flip with back-ease pop,
best-last staging by rarity-then-buylist-value, commons batch-flip button on
3+ runs, buildup pulse+shiver on the final card, first-pull glint sweep + NEW
badge, revealed row, long-press zoom no-peek) and batch (starters + Open All:
rapid cascade, hard auto-pause on rare+/notable, soft 0.7s hold on new
uncommons, pack-art interstitials, tap pause/resume). First-pull computed
from the acquisition log (opening seq vs oldest event; duplicates glint
once). D2-backlog art preload folded in: bounded 8s blocking preload +
one-ahead texture pre-touch. Sound pass from stock audio (shuffle/flip_card/
draw/take_shard/coins_drop) + HapticEngine. Summary spread: grid w/ NEW
badges, buylist total, Open another/Open all continuation. All pacing
constants sit in one block atop `ChronicleRevealScene` — the dogfood tuning
surface. Suite 34 green; mobile-dev jar boots clean. **The done-when stays
open by design (experiential bar, author-judged; iterate through D5).**
Residue: gather Pocket reference footage for the side-by-side.
*Live round 1 CLOSED same evening (5 commits → `ba94fc4cfd`; devlog
2026-08-01-session5):* dev-mode testing actions (home-screen day
advance via tick-marker rewind — clock-scum guard untouched, seed
integrity holds by day-index determinism — plus test cash), booster art
actually fetching (stock `imageKeyFileExists` bug meant it had NEVER
downloaded — binder tiles included), reveal-NEW cross-checked against
collection counts, cascade pacing slowed + first-pull soft holds,
pulsing tap-to-continue pill, row long-press hit-test, EDT-hopped
fetches. Starter deck-box art blocked upstream: `downloads.cardforge.org`
has no DNS record and forge-extras mirrors no tournament packs — fetcher
`o:` support shipped anyway (generalized `fetchProductImage`, upstream
candidate) and starters draw booster-art fallback that self-upgrades if
the images are ever rehosted. Original
spec: Bar DEFINED (sketch, "Reveal-UX bar v1" — all four
pins user-taken 2026-07-31): **period-wrapper identity evolving with the
timeline** (the reveal object is the set's real booster art via
`ImageKeys.BOOSTER_PREFIX`; foil-era gloss debuts with the 1999 event; Pocket's
interaction grammar without its aesthetic), **tier 2 mechanics** (rip/drag to
open with a REAL animated wrapper-tear — no 3D pack, user pin, 2.5D
throughout; tap-to-flip player pacing, commons batch-flip, rare-slot buildup,
NEW glint; tier-3 polish = post-dogfood), **both registers day one** — single-pack
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
*Scouted 2026-08-01:* the module is `forge-gui-android` (in the reactor),
built via the `android-debug` profile (`packaging.type=apk`,
simpligility android-maven-plugin); it expects **Android SDK build-tools
35.0.0 + platform 35** — no SDK on the box yet, so the spike's first step is
an SDK install (user decision: several GB + license acceptance), then
`mvn -P android-debug -pl forge-gui-android -am package` and adb sideload.
*BUILD PATH SOLVED 2026-08-02 (fork `6f6273ac3c`, `scripts/build-android.sh`
= the whole recipe):* SDK installed to `~/Android/Sdk` (user-approved);
three CI-parity pins discovered the hard way — **Maven 3.8.1** (the plugin
breaks on 3.9+), **Temurin 17** (proguard 7.6 reads `<java.home>/jmods` as
library jars and rejects >Java-23 class files), and **android-maven-plugin
4.6.2 is a Card-Forge custom build** fetched into `~/.m2` from their GitHub
releases, not Central. In-process jarsigner is dead on JDK 17+
(`sun.security.pkcs` sealed) — profile flipped to external
`uber-apk-signer` signing (v2+v3, `~/.android/debug.keystore`; KEEP that
keystore — update continuity). **Coexistence with stock Forge (user pin):**
package renamed at aapt time to `forge.app.playable` (own launcher entry
"Forge Playable", own `Android/obb` data dir; `forge.app` substring
preserved so `usingAppDirectory` still trips; upstream's `resId()` fallback
anticipated the rename) + the three FIXED provider authorities
(`com.mydomain.publicfileprovider`, `.Sentry*Provider`) made unique — any
second install sharing an authority is REJECTED by Android, so stock's
presence would have blocked the install outright. **Update delivery
un-deferred (user request):** the stock in-app updater (AssetsDownloader)
already targets the fork's `GITHUB_SNAPSHOT_URL` = `daily-snapshots`;
published the android artifact set there (APK named exactly as the updater
expects + `assets.zip` 194M incl. `res/chronicle/` + shared
`version.txt`/`build.txt` stamps — desktop delta updater absorbs the bump
as a 0-file plan). First boot downloads assets from the same URL. Caveat:
android update offers gate on **>23h** build.txt delta (upstream rule);
desktop-style strictly-newer is a 1-line fork change if dogfood cadence
needs it. APK delivered via Syncthing (`~/Everything/Sync/Other`);
on-device boot = the remaining done-when.

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
- Stage-2+ design threads in the sketch: implementable market spec is now the
  only remaining design lift. Famous-card allowlist CLOSED to design
  2026-07-31 (sketch "Famous-card allowlist v0": path-shaping-only purpose,
  story-per-entry event-anchored schema, backout-consistency rule, ~12-entry
  seed, seed+calibrate authoring; residue = writing the seed file rows —
  data work, D1 for the 1994 column / stage 2 for event legs). Per-product
  tier data file: MVP-window rows are trivially D1 work. Completion-award selection ADVANCED 2026-07-31
  (sketch "Awards round 2"): first pass = avatars (crop derivation) +
  Chronicle-clipping scrapbook; sourcing principles pinned (runtime
  derive-from-card-art, no baked/generated assets in the repo); aesthetic
  north star noted (purposeful-retro lo-fi), decision deferred.

## Risks

- **The reveal scene is the quality bar** — the one module where "buildable as
  written" doesn't apply. Mitigated by sequencing it after the loop exists (D3)
  so iteration happens against a playable game.
- **forge-android pipeline unknowns** — upstream builds it, our release
  pipeline is desktop-jar-only. The parallel-early spike (D4) retires this well
  before the gate needs it.
- **Hours competition with M4** — the standing risk, unchanged; the stages
  above are independently shippable chunks per the sketch's mitigation.
