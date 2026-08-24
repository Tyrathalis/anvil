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
(language dormant, condition never), ~~kitchen-table play = stretch~~
**kitchen-table play PROMOTED to D6 (2026-08-22, [ADR-0070](../decisions/ADR-0070-chronicle-effort-reward-sink.md))
— the dogfood measured the missing effort→reward channel.** Foils,
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

## New pin from the D5 dogfood (user, 2026-08-22)

8. **The mode must contain an effort→reward channel** — somewhere that
   *invested time converts into progress*. Grants on a daily timer are not one.
   The shipped MVP loop is all grants (ration, stipend) plus a buylist that
   pays out less than packs cost by construction, so there is no action whose
   reward scales with how much you put in; the dogfood named that as the thing
   that ends the daily habit. This sits **above the MVP/stage line** — a
   property of the design, not a stage-2 feature — and it outlives D6: if D6's
   purse doesn't satisfy it, the pin stands and the next candidate is scoped
   against it. Full reasoning + the open questions: [ADR-0070](../decisions/ADR-0070-chronicle-effort-reward-sink.md).
   **Answered on both halves 2026-08-22** ([ADR-0071 addendum](../decisions/ADR-0071-d6-design-round.md)):
   bounded cash income protects the economy, unbounded ante satisfies "put more
   time in, get more out". Deliberate asymmetry — the grinder is pushed into the
   *subtractive* channel by design; risk is the price of unbounded.

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
**Dogfood round-1 tear rework LANDED 2026-08-22 (`2177e66f6d`)** — two findings from
the author's phone round, both in the tear, both real defects rather than taste:
(1) *the gesture was not a swipe* — `pan()` accumulated `Math.abs(deltaX)`, so
the return stroke added progress exactly like the pull did (a shake opened a
pack; a half-swipe-and-back finished the tear instead of releasing it), nothing
handled the finger lifting, and `TEAR_DRAGS_TO_OPEN` was 1.1 *screen widths* —
physically uncoverable in one swipe, so `fling()` was the only real way in. Now:
direction commits on first horizontal travel and only travel that way counts,
pulling back closes it proportionally, `panStop` springs it shut on a short
release, `fling` completes only along the committed axis+direction, and progress
is measured from an anchor against absolute x (correct across lift-and-resume);
one committed swipe over half the screen width opens a pack.
(2) *the animation was a tilt, not a tear* — the strip above the tear line was
one rigid quad slid right and rotated ≤7°. It is now 16 vertical columns, each
whole until the tear reaches it then split at its own point on a stable per-pack
zigzag, peeling with a lag from the gripped end so the split **propagates** as
you pull; each column slides/rises/curls by its own progress, the fresh edge
draws as one connected bright zigzag, and the peel follows the direction torn.
New constants join the pacing block (`TEAR_SWIPE_FRACTION`, `TEAR_SEGMENTS`,
`TEAR_JAG_FRACTION`, `TEAR_PEEL_LAG`, `TEAR_CURL_DEG`, `TEAR_LIFT_FRACTION`,
`TEAR_SLIDE_FRACTION`, `TEAR_SPRING_RATE`, `TEAR_FLING_MIN`). Compiles clean;
**on-device feel not yet verified** (held while `d6-run19` had the box).
Register considered and NOT taken: a pixelated wrapper-dissolve — the retro-lo-fi
north star admits it, but it reads digital against the period booster art it
would be dissolving, and the D3 bar pinned a real paper tear.
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
needs it. APK delivered via Syncthing (`~/Everything/Sync/Other`).
**DONE 2026-08-22: done-when met** — the author has been running the daily
pack-opening loop on the phone (that round's findings are D3's tear rework and
[ADR-0070](../decisions/ADR-0070-chronicle-effort-reward-sink.md)). Recorded
retroactively; the on-device boot was never written up when it happened.

**D5 — dogfood + numbers. OPEN; the two-week clock can start now that D6 is
playable (2026-08-24). Round 1 read 2026-08-22.** Two weeks of real
daily use by the author (on the phone, per the design's mobile-first lean), plus
the tuning pass: ration size (2–3 packs?), MSRP/buylist/stipend table, allowance
cadence (weekly lump vs daily). *Exit criterion:* the daily loop still feels good
after ~2 weeks — then flip the visibility pref for friends (beta), and take the
courtesy Discord float. A failed exit is design feedback for the sketch, not a
death sentence.

*Round 1 (2026-08-22, phone):* three findings. Two were reveal-scene defects,
fixed in D3 above (the abs-delta swipe; the tilt-instead-of-tear). The third is
the design result and got its own ADR: **the loop has no effort→reward channel**
(pin 8 / [ADR-0070](../decisions/ADR-0070-chronicle-effort-reward-sink.md)) —
"nothing to do with the cards but look at them." It promotes the kitchen-table
stretch to D6 and pushes the numbers pass behind it.

**Ordering decided with the round-1 read (user):** the numbers pass is
**deferred behind D6**. Ration size, stipend cadence and the MSRP/buylist tables
are all still at their seed defaults, and a purse changes what every one of them
should be — tuning a fixed-weekly-income economy that is about to gain a
variable income source is wasted work. The two-week dogfood clock effectively
restarts when D6 lands, since the loop being dogfooded changes shape.

**D6 — kitchen table + purse (the effort→reward sink). BUILT 2026-08-22
(fork `playable` @ `c647ba081e` headless + `92708b5452` screens); VERIFIED IN
PLAY 2026-08-24 — the author has built decks and played rival games on device.**
Chronicle suite 71 green, full desktop suite 520/0/11-skipped. Shared-file
footprint ended at three files (an `ItemManagerConfig` enum entry, an
`SColumnUtil` column set, and a generic `ImageView` pile-by fix — all additive
and upstreamable), having started at zero.

*Getting from BUILT to PLAYABLE took four rounds of defects that only play could
find (v18–v22; devlog [2026-08-23-session2](../devlog/2026-08-23-session2.md)),
and the record matters more than the fixes:*
- the tear peeled from the wrong edge (one inverted sign);
- the editor crashed on open — `ColumnDef.NEW` ships null sort/display functions
  ("functions will be set later"), so **every consumer must supply them via
  `getColOverrides`**; reusing Quest's config without Quest's contract throws
  before a card is drawn;
- `ImageView`'s pile-by dereferenced the raw static `fnSort`, which any config
  carrying NEW/PRICE/OWNED/DECKS can reach — **upstream candidate**, Quest
  included;
- Chronicle was borrowing `QUEST_EDITOR_POOL`, and `ItemManagerConfig` holds
  *persisted* per-config view state, so the two modes silently reconfigured each
  other → `CHRONICLE_DECK_POOL`;
- **the empty catalog's root cause was ours:** `IDeckController.setEditor` must
  also call `editor.notifyNewControllerModel()`. Without it `FDeckEditor.getDeck()`
  stays null through construction, `CardManagerPage.initialize()` never calls
  `onDeckChanged`, `needRefreshWhenShown` is never set, and `CatalogPage.refresh()`
  never runs — an editor that opens cleanly and shows nothing, forever;
- and a pre-D6 save showed no rivals because `rivals.txt` was the only Chronicle
  data file introduced *after* that install's `assets.zip`.

*Two conventions were born from that and belong with the architecture decisions
above:* **(a)** small curated data that ships with a feature also ships inside
the jar/APK as a classpath resource (res/ wins when present so the file stays
moddable; a test pins the two copies byte-identical) — res/ arrives by asset
delta and can lag the code that needs it, or never arrive at all; **(b)** a
libGDX screen defect cannot be found by reading or tested from the desktop tree,
so **drive the build**: isolated `-Duser.home`, `xdotool` for input,
`import -window` for capture (the Wayland compositor screenshot cannot see the
XWayland surface), and probe by writing to a file, because Forge's own logging
stops at boot and console silence reads as "the code never ran".
*Promoted from "Stretch" 2026-08-22 by [ADR-0070](../decisions/ADR-0070-chronicle-effort-reward-sink.md);
the highest-value remaining Chronicle work, though explicitly not required to be
the immediate next commit.*

*Built (headless, `forge-gui/.../gamemodes/chronicle/`):* `ChronicleRival` +
`ChronicleRoster` + `res/chronicle/rivals.txt` (5-kid seed cast);
`ChronicleRivalPool` — a rival's collection is DERIVED, never stored, from
(run seed, rival id, **pack index**) and deliberately not the day, so pack *i*
is the same pack forever, day D+1's pool contains day D's, and the save stores
nothing for it; pack *i* has a computable acquisition day and can only hold a
product **released** by then, which is the entire difficulty model (a rival
keeps what they bought, so the pool spreads across more and stronger sets as the
timeline advances — `packsPerDay` is that kid's allowance and there is no power
knob anywhere). `ChronicleDeckSource` = the ADR-0071 pool-in/deck-out seam;
`ChronicleDeckBuilder` fences forge-core's generator against three things it
doesn't do for us — it's **count-blind** (DeckGenPool keys by name, so one Lotus
yields four) and gets clamped to owned counts, it picks colours at random and
instead gets the two the collection is deepest in, and **basics aren't in the
pool at all** (Forge's era sheets put none in 1993-94 boosters, so a pack-only
rival owns zero lands) so they're supplied outside the collection in a period
edition. Determinism came free: every forge-core generator routes randomness
through `MyRandom`, exactly like `BoosterGenerator`. `ChronicleDecks`
(reference-only; shortfall reported, never a silent rewrite of the player's
deck), `ChronicleKitchen` (purse once per rival per played day; a loss doesn't
burn the day), config knob `pursebaseCents`, run save/load + controller API.

*Built (mobile):* home-screen Kitchen Table entry carrying the count of purses
still uncollected today; `ChronicleKitchenScreen` (who's around, what they pay,
your record, "Rematch (no money on it)" once collected); `ChronicleDeckScreen` +
a small `IDeckController` routing the **stock** `FDeckEditor` into the run —
decks live in the Chronicle save, NOT Forge's shared deck store (load-bearing:
the playable build shares that store with the research harness, whose
`launch --pool` gates on installed-deck content hashes); the editor's only hook
is `setPlayerInventorySupplier` pointing the catalog at the collection, which is
Quest's existing semantics and exactly the chosen legality.

*`ChronicleMatch` needed NO shared-file change* — Adventure reports results via
an `isMobileAdventureMode` branch inside `MatchController.finishGame()`; a second
mode branch there is what the isolation convention exists to avoid, and
`HostedMatch.setEndGameHook` + `getGame().getOutcome().isWinner(...)` makes it
unnecessary. Two rules pinned at the table rather than inherited: **one game,
not a match** (best-of-three is a tournament construct; also makes the purse
unambiguous) and **ante forced OFF** — the global `UI_ANTE` preference must never
reach this table, since ADR-0071 makes ante opt-in and the opt-in doesn't exist
yet, so inheriting it would silently gamble the player's collection.

**ANTE BUILT same day (`111a441f74`) — the grind shape RESOLVED as two speeds**
([ADR-0071 addendum](../decisions/ADR-0071-d6-design-round.md), user
counter-proposal, better than the plan's recommendation): **cash stays bounded,
ante is unbounded and priced in risk instead of time.** Checked against the
implementation rather than argued — by volume ante is a poor card source (1 card
per won game ≈ 4–10/hour flawless, vs 30 free cards/day from the ration), and
`Game.chooseCardsForAnte` draws a rarity **uniformly over the classes both
libraries share**, so ~1-in-3 games has a rare on the table (vs 1-in-15 in a
pack) — meaningful, gated behind winning, and symmetric since the player stakes
their own at the same rate. Self-limiting three ways rather than by a timer: you
stake from your own deck, the rival's pool really depletes, and they decline
below `anteRivalFloorCards`.

*The architectural consequence, and a mechanic that disappeared:* rival pools
were seed-pure with zero save state, and ante moves real cards. Resolved by
persisting only a delta (`ChronicleRivalLedger`) —
`pool = derived(packs by day) − lostToPlayer + wonFromPlayer`. **The catch-up
mechanic proved unnecessary:** the derived term keeps growing on schedule, so a
stripped rival recovers as their allowance rolls in — no rubber band, nothing to
tune, no engagement-trap spring. It also **bounds the world's card supply**
(total extractable ≤ the derived curve), so an unbounded match channel cannot
outpace the release calendar and the scarcity engine survives. Free consequences:
a stripped rival plays a worse deck (difficulty self-corrects in fiction), and
"run out of spares" is a real, legible state.

*Stakes:* Forge's real ante — random card from the deck, rarity-matched, basics
excluded, winner takes both, via `GameOutcome.AnteResult`. Your best cards are
both win condition and collateral (period-authentic; ante-proofing was real).
Loss is permanent under seed integrity, so a confirm says so plainly, and ante
is **never** inherited from the global `UI_ANTE` preference.

*The journal now records departures.* `ChronicleAcquisitionLog` gains a `Source`
enum (BOOSTER/STARTER/ANTE_WON/ANTE_LOST) keeping `SealedItem.Kind`'s names so
pre-ante saves load unchanged; an ante win takes a first-pull ordinal. "Lost to
Marcy, day 34" shows in the binder's provenance popup.

*Not yet built / next:* on-device verification of the whole loop; the paper's
rival hooks (`ChronicleRoster.joiningOn` exists, unused, for the "new kid at the
table" headline). *Open at tuning time:* whether 1-in-3 rare stakes is too
generous or too punishing; whether `anteRivalFloorCards` should scale with tier;
cast size and growth rate. Deck editor wiring + ownership-legality over the
printing×finish inventory (1993–94 casual play predates formats; the format
resolver arrives with the tournament board), play against the AI, and a **purse**
on the result. Deck editor, AI and match runner all already exist in Forge —
this is wiring plus an economy line, not new machinery. Period fidelity holds
and constrains it: kitchen-table play in 1993–94 is period-correct; it is
venues, organized play and tournament income that would be anachronistic, and
those stay out (stage 2/3, sketch layer ordering unchanged).

**Design round DONE 2026-08-22 ([ADR-0071](../decisions/ADR-0071-d6-design-round.md)).**
All three ADR-0070 questions settled, plus the two the build forced:

1. **Purse = cash by default, ante = opt-in stake at a better payout.** Ante as
   the *default* inverts the mode's core loop — everything in Chronicle is
   accumulation, and ante makes the primary reward channel **subtractive from
   the collection**, so a loss undoes earlier sessions (and seed integrity makes
   it permanent). As a *choice* it is both period-accurate (playing for ante was
   a decision, not the default) and adds a **risk** axis to effort→reward.
2. **Opponent = a small cast of named rival collectors**, each with a seeded
   collection that grows along the player's own timeline; the rival's deck is
   generated from *that rival's* pool. Difficulty then rises with the era for
   free, in fiction; the paper gains its first narrative content; and the
   period-correct opponent genuinely is another kitchen-table player with a jank
   collection. Rival acquisitions derive from (run seed, rival id, day index) —
   seed integrity extends unchanged.
3. **Legality = reference-only: decks borrow, they don't consume.** Per-deck copy
   limits still apply. This is already what `DeckEditorConfig.usePlayerInventory()`
   means in Quest, so it's the default behaviour of machinery we're reusing.
   Reservation semantics rejected for now (would give duplicates real value, but
   needs save-schema state + UI before the loop is proven).
4. **Generation = `DeckGeneratorBase` over a `DeckGenPool`** built from the
   relevant collection. Period `.thm` archetype files are an optional later
   layer, not D6 scope.
5. **Anvil is the designed long-run replacement** (sketch layer 3's sim probe →
   Tutor's scorer). Not D6 work — but rival-deck construction goes behind a
   narrow seam (pool in, deck out) so the swap costs nothing later.

*Fork archaeology (ADR-0071): D6 needs no new machinery.* `DeckGeneratorBase`
takes an arbitrary `PaperCard` pool (Chronicle's collection already is one);
`FDeckEditor.DeckEditorConfig` exposes `getCardPool()` + `usePlayerInventory()`;
`MatchController.hostMatch()` + `startMatch(...)` with
`forge.adventure.scene.DuelScene` as the harvest template.

*Finding of record:* **there is no corpus of period decklists, and that's
historically correct** — 1993–94 predates published deck tech, and the earliest
documented lists post-date the window's close at FEM. All three shipped Forge
deck corpora are anachronistic for it (LDA archetype models cover
Modern/Legacy/Historic/Pauper, and Legacy's archetypes are Sneak Show and
Merfolk; the 505 quest precons are modern WotC precons; the 786 `geneticaidecks`
are GA-evolved Legacy). Nothing to import, and importing would be wrong.

*Still open — the live question, and where pin 8 gets tested:* **the grind
shape.** Unbounded paying rematches are an income exploit and sit badly with the
no-engagement-traps stance; a hard daily cap partly defeats pin 8. Recommended
shape, to be **confirmed by dogfood rather than pinned**: one paying challenge
per rival per in-game day, rematches always playable and always free but paying
nothing, purse scaling with rival difficulty, cast growing with the timeline —
so time converts into progress through *deck quality and harder opponents*, not
repetition. Also open to build time: cast size and growth rate; whether a
rival's pool is stored or regenerated from seed (cheaper, matches the seed
posture, but needs a versioned generator).

*Economy knock-on (unchanged from ADR-0070).* Packs stay EV-negative (invariant
untouched), but total inflow stops being a fixed weekly constant in both amount
and cadence, so the D5 numbers pass has to be re-derived against a
variable-income loop — now with a second axis, purse-per-difficulty and the ante
multiplier. The Ante ledger gets its first honest use: an opt-in stake is
literally what the module was named for, and it should be accounted from the
first commit.

## Open items (tracked, not blocking)

- ~~Reveal-UX bar definition~~ CLOSED 2026-07-31 (sketch "Reveal-UX bar v1";
  D3 above carries the operative form). Residue: gather Pocket reference
  footage at D3 build time.
- Numbers pass: ration size, MSRP/buylist/stipend, allowance cadence — **D5,
  deferred behind D6** (a purse re-derives all of them; ADR-0070).
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
