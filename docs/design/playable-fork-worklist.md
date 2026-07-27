# Playable-fork worklist

Notes for a **human-facing build** of the Forge fork — distinct from the
pinned research fork Anvil trains against. Prompted 2026-07-26: friends are
weighing Forge against Tabletop Simulator for a 1v1/multiplayer Commander
night.

These are **notes and nice-to-haves, not a scheduled milestone.** Nothing here
is on the M3/M4 critical path.

## Fork-discipline note — this is a separate branch, not the pinned commit

The research fork is pinned as the M4 teacher/opponent and must stay
byte-deterministic on the headless game path (fork-discipline convention;
[ADR-0025](../decisions/ADR-0025-d4-rebase-closeout.md)). **Every item here
lives in UI / net-transport / auto-updater / deck-import code** (`forge-gui`,
`forge-gui-desktop`, `forge-gui-mobile*`) — modules the headless training
harness never loads (it drives the engine over the gRPC bridge, no Swing/libGDX,
no Netty multiplayer stack). So these changes are training-neutral by
construction.

Still, keep them on a **separate `playable`/distribution branch** off the
pinned commit rather than committing them onto the commit used for training
runs — the pin is a dataset boundary and should carry zero incidental drift.
Rebase the `playable` branch forward independently. (If any item ever needs an
engine-path change, it stops being training-neutral and gets forkcheck-gated
like any other engine bump.)

---

## 1. Auto-updater UX: in-place update instead of dropping an installer in Downloads

The Adventure Mode (mobile-dev) launcher on Linux runs the libGDX updater in
`forge-gui-mobile/src/forge/assets/AssetsDownloader.java` (`checkForUpdates`,
non-Android branch). On an available update it:

1. downloads `forge-installer-<version>.jar` (snapshot channel) into the
   Downloads dir (`GuiDownloadZipService(...).download(filename)`),
2. `Forge.getDeviceAdapter().openFile(installer)` — hands the jar to the OS,
3. exits the app.

(The Swing desktop path is the twin: `forge/download/AutoUpdater.java` →
`downloadFromForge()` writes `<version>-upgrade.jar` to `~/Downloads/`, opens
it, `System.exit(0)`.)

That's the "it wanted to save a snapshot file" behavior — the user is left to
run a full installer GUI and gets an installer jar cluttering Downloads each
time.

**User-confirmed 2026-07-26** (independently, from play): the mobile UI on
desktop Linux does prompt to update, and the update "asks you to save a new file
to a new location" instead of applying in place. One detail to pin when
reproducing: whether a **save-as dialog** actually appears, or whether the file
lands in Downloads silently and the *installer* it hands off to
(`openFile(installer)`) is what prompts. The code path above suggests the
latter, the recollection suggests the former, and they imply different repro
steps. It changes nothing about the fix — applying in place removes the prompt
either way — but pin it before writing the fix so the "before" is described
accurately.

**Nice-to-have:** apply the update in place and auto-restart — download to a
temp/staging dir (not Downloads), swap files, relaunch — no manual installer
step, no leftover artifact. The libGDX/desktop launcher already relaunches
itself (`DesktopAdapter.restart()` / `RestartUtil`), so the missing piece is a
silent apply-then-restart path rather than `openFile(installer)` + exit. Pairs
naturally with item 2 (once the payload is a delta, in-place apply is cheap).

---

## 2. Incremental / delta update download instead of the full ~160–270 MB package

Every accepted update re-downloads the **entire** package
(`AssetsDownloader` advertises `packageSize` = `"270MB"` desktop / `"160MB"`
Android; the release/snapshot channels fetch the whole
`forge-installer-*.jar` / `assets.zip`). Nothing on the wire is diffed against
what's already installed.

**Nice-to-have:** ship a per-file manifest (path + content hash) with each
build and download only changed entries — most updates change a handful of card
scripts and a few res files, not the whole tree. Implementation sketch:

- Publish `manifest.json` (or reuse `build.txt` + a hashes file) alongside each
  release/snapshot on the fork's GitHub.
- On update, fetch the manifest, diff against the local install's hashes, pull
  only the changed/added files, delete removed ones.
- Confirm during implementation exactly which payload the Linux Adventure
  launcher pulls (the non-Android branch downloads the installer jar; the
  `assets.zip` resource block in `AssetsDownloader` is Android-only) — the
  observed ~160 MB is the installer/package re-pull, and the delta target is
  whichever payload that resolves to. Pin the number empirically.
  **User-confirmed 2026-07-26** (independently, from play): the ~160 MB pull is
  real, happens on the **mobile UI on desktop Linux**, and arrives as an "extra
  data download" *after* the update prompt — i.e. it is a second transfer
  following the update itself, which is a useful discriminator for identifying
  the payload. That observation is the empirical anchor this bullet asked for;
  still confirm which code path serves it before designing the diff.

Related: the same idea sits in
[upstream-worklist.md](upstream-worklist.md) as a queued upstream idea (HTTP
Range requests into `assets.zip` as the zero-hosting-change variant).

---

## 3. Point the updater at our own fork's GitHub, not Card-Forge upstream

The update sources are hardcoded to upstream in
`forge-gui/src/main/java/forge/localinstance/properties/ForgeConstants.java`:

```
GITHUB_FORGE_URL     = "https://github.com/Card-Forge/forge/"   (:30)
GITHUB_RELEASES_ATOM = GITHUB_FORGE_URL + "releases.atom"       (:31)
GITHUB_COMMITS_ATOM  = GITHUB_FORGE_URL + "commits/master.atom" (:32)
GITHUB_SNAPSHOT_URL  = GITHUB_FORGE_URL + "releases/download/daily-snapshots/" (:33)
RELEASE_URL          = "https://releases.cardforge.org/"        (:35)
```

**Change:** repoint `GITHUB_FORGE_URL` to the fork (`origin` =
`https://github.com/Tyrathalis/forge/`). That redirects the atom feeds, the
snapshot download URL, and the release-download URL (built from
`GITHUB_FORGE_URL + "releases/download/..."`) to our repo in one edit.

**Caveat:** the *release* channel also uses `RELEASE_URL`
(`releases.cardforge.org`, a separate Maven-style host) for `maven-metadata.xml`
and `.tar.bz2`. We don't run that host. Simplest path for a fork: publish
GitHub-hosted **snapshot-style** releases (tag + `version.txt` + `build.txt` +
package under `releases/download/…`) and drive the "snapshot" update channel,
which is entirely GitHub-hosted — avoids standing up a cardforge-style release
server. Confirm `getReleaseTag`/`getLatestChanges` (RSSReader over the atom
feeds) parse our repo's release/commit atoms.

---

## 4. Window resizing in Adventure Mode / the mobile build on desktop Linux

The Adventure Mode build (`forge-gui-mobile-dev`, the libGDX/LWJGL3 desktop
launcher that also drives Adventure) does not resize properly on desktop Linux.
**Wanted:** resizing that behaves like a normal desktop window, ideally
including **corner/edge snapping** (half-screen and quarter-screen tiling —
KWin/GNOME-style drag-to-edge).

**Diagnosed 2026-07-26. Not fork-specific.** `GameLauncher.java` is
byte-identical between our pinned base (`3e3818f1ba`) and upstream, and
upstream's tip touches the file only for an unrelated window-focus refactor
(`Forge.setWindowFocus` → `SoundSystem.instance.setWindowFocus`). This is stock
upstream behavior, so it is an upstream-PR candidate, not a fork wart.

Three layers, in increasing depth:

**L1 — the window is declared non-resizable.**
`forge-gui-mobile-dev/src/forge/app/GameLauncher.java:118`:

```java
} else {
    config.setWindowedMode(windowWidth, windowHeight);
    config.setResizable(false);
}
```

GLFW then publishes fixed min=max size hints, and KWin/GNOME refuse to tile a
window advertising fixed size hints. **That one line explains the missing
corner/edge snapping by itself**, independent of anything in the app's layout
code — the compositor never even offers the tile.

**L2 — the render loop draws at a launch-time size.**
`forge-gui-mobile/src/forge/Forge.java:206` captures `screenWidth`/`screenHeight`
once, with the comment *"should be set initially and only change upon restarting
the app"*. Those statics drive `render()` every frame:
`graphics.begin(screenWidth, screenHeight)` (:991),
`screen.screenPos.setSize(...)` (:992), overlay sizing (:1002). `Forge.resize()`
(:1040) forwards the new size to `currentScreen.setSize(...)` and
`currentScene.resize(...)` but never updates the statics — so flipping L1 alone
yields a window that resizes around a stale viewport.

**L3 — the UI scale factor is frozen at class-init.**
`forge-gui-mobile/src/forge/util/Utils.java:12` declares `SCREEN_WIDTH`,
`SCREEN_HEIGHT` and `HEIGHT_RATIO` as `static final`, read from `Gdx.graphics`
at class load. `Utils.scale()` feeds fonts, `FCardPanel.PADDING`, and
`AVG_FINGER_WIDTH/HEIGHT` — every touch target and font size in the mobile UI.
A live resize does not rescale any of it. Related: `isPortraitMode` is decided
once from the initial aspect (`Forge.java:210`), so crossing the square boundary
should really swap the whole layout family.

### Tiered plan

- **T1 (small) — resizable window + live viewport.** `setResizable(true)`,
  `setWindowSizeLimits(minW, minH, -1, -1)` for a sane floor, and update
  `screenWidth`/`screenHeight` inside `Forge.resize()` before forwarding. Leaves
  L3 alone: fonts and touch targets stay at launch scale, which reads fine
  within roughly ±40% of the launch size and visibly off beyond it. **This is
  the tier that unlocks compositor snapping.** Ship it first and play a real
  game on it before deciding whether T2 is wanted.
- **T2 (medium) — rescale on resize-end.** Make the `Utils` ratio a settable
  static recomputed from the current backbuffer, and regenerate FSkin fonts on a
  **debounced** resize-end — font regeneration is far too expensive to run
  per-frame during a drag. The real work is the audit: find every `static final`
  that transitively reads `Utils.scale()` at class-init time. Changing them is
  trivial; finding them is not.
- **T3 (larger, optional) — orientation flip.** On crossing the square
  boundary, re-derive `isPortraitMode` and rebuild the screen stack. Highest
  blast radius of the three. Skip unless someone actually tiles the window into
  a portrait half.

### Acceptance

Window drags to arbitrary sizes without stale-viewport artifacts; KWin
drag-to-edge tiles it to half and quarter screen; a full match is playable at
both a half-screen and a maximized size; relaunch still restores the
config-file size. Check **both X11 and native Wayland** — the GLFW backend
differs, and snapping semantics with it; record which backend the launcher
actually gets rather than assuming.

Upstream: T1 is small, self-contained and defensible — same shape as #11203 /
#11285. Land it in the fork, verify it on the Commander night box, then offer
it upstream with the compositor-size-hints rationale. Training-neutral either
way (`forge-gui-mobile*` is never loaded by the headless harness).

---

## 5. Shallower / configurable tap rotation angle

Both clients rotate a tapped card a full 90°. **Wanted:** a shallower tilt
(Arena/MTGO-ish), ideally a preference rather than a new hardcoded constant, so
tapped cards stay legible and the battlefield row reflows less.

> **Paired with the upstream entry.** The same idea is queued as an upstream
> pitch in [upstream-worklist.md](upstream-worklist.md) ("Queued idea —
> configurable tap angle", 2026-07-26), which carries the archaeology: **no
> GitHub issue or PR discussion exists** on tap angle / tapped rotation — nobody
> decided against it, it is simply unbuilt; the nearby prefs
> (`UI_ROTATE_PLANE_OR_PHENOMENON`, `UI_ROTATE_SPLIT_CARDS`,
> `UI_ANIMATED_CARD_TAPUNTAP`) are unrelated; and per house survey lore the idea
> should be floated in Discord before code is written. **This file builds it;
> that file pitches it. Keep the pref name and the value list identical across
> the two.**
>
> That entry flagged one risk — desktop's image path rounds rotations to the
> nearest 90° (`FImageUtil.getRotationToNearest`). **Checked 2026-07-26: it does
> not apply.** The rounding lives in `FImagePanel`, the zoomer/detail component.
> The battlefield card uses `ScaledImagePanel` inside a `Graphics2D` that
> `CardPanel.paint():307` rotates by an arbitrary angle — a live
> `AffineTransform`, no image-cache rounding on the path. Arbitrary angles are
> safe on desktop.

The angle itself is one line per client. The work is that **three geometry
consumers hard-assume exactly 90°**, and they are precisely the ones that fail
silently — the card gets drawn somewhere you cannot click.

**Mobile** (`forge-gui-mobile`):

- `FCardPanel.getTappedAngle():70` → `-90`; overridden in
  `VCardDisplayArea:595` (negated for 180-rotated fields).
- `FCardPanel.CardUnTapAnimation.drawCard:288` hardcodes
  `-90 + (percentage * 90)` instead of delegating to `getTappedAngle()` — **a
  latent bug that activates the moment the angle becomes configurable** (the
  untap animation would sweep from the wrong start angle). Worth fixing on its
  own regardless of this item.
- `FCardPanel.renderedCardContains:74` — hit-test swaps `w`/`h` and shifts
  `top += h - w`. Exact-90 assumption.
- `VCardDisplayArea.getTargetingArrowOrigin:560` — same swap, for arrow anchors.

**Desktop** (`forge-gui-desktop`):

- `CardPanel.TAPPED_ANGLE:89` = `Math.PI / 2`, applied in `paint():307`
  (`g2d.rotate` about `(cardX + w/2, cardY + h - w/2)`) and set in
  `PlayArea:1052`.
- `PlayArea.getCardPanel(x, y):718` — hit-test swaps `cardWidth`/`cardHeight`
  and shifts `panelY`. Same exact-90 assumption as mobile.
- `PlayArea:775 / :790 / :808` compare `getTappedAngle() != TAPPED_ANGLE` as an
  "animation still in flight" guard. These keep working at any angle **provided
  the comparison stays against the same configured value**, not a literal.
- Useful precedent already in tree: `CardPanel:647` inverse-rotates the mouse
  point into card space for the badge hit-test. **That is exactly the technique
  both card hit-tests should adopt** — no new math to invent.

### Plan

1. **Generalize the hit-tests first, with the angle still 90.** Replace the
   exact-90 w/h swaps in `FCardPanel.renderedCardContains`,
   `VCardDisplayArea.getTargetingArrowOrigin` and `PlayArea.getCardPanel` with
   inverse-rotate-then-test-unrotated-rect (the `CardPanel:647` method, lifted
   into a small helper per client). Behavior must be pixel-identical at 90° —
   that identity *is* the check that the refactor is correct, and it is worth
   doing as its own commit.
2. **Route the angle through one accessor per client**, and make the untap
   animation delegate to it (kills the `:288` duplicate).
3. **Add the preference.** `FPref.UI_TAP_ANGLE` in `ForgePreferences.java`
   (name taken from the upstream entry — do not diverge), default `"90"` so
   stock behavior is preserved for anyone who doesn't touch it. Rendered as a
   `CustomSelectSetting` in mobile `SettingsPage.java` (+ adventure
   `SettingsScene.java`, which mirrors a subset of the same prefs) and as an
   `FComboBoxPanel<String>` in desktop `VSubmenuPreferences` /
   `CSubmenuPreferences` — both widgets already exist in those files.

   Offer a short value list (**90 / 75 / 60 / 45**) rather than a free slider or
   text field. The upstream entry suggests copying
   `UI_ACTIONABLE_HIGHLIGHT_COLOR` as the both-UIs precedent; that is the right
   precedent for *validation* but not for the widget — it is free-form text and
   needed a bespoke `HexColorSetting` class on mobile, whereas a discrete list
   reuses `CustomSelectSetting` and adds no new class. **Do** copy its
   defensive read: `CardPanel:416-420` parses the pref and falls back to
   `FPref.getDefault()` on anything unparseable. An angle read from a config
   file deserves the same treatment.
4. **Layout reservation: keep the 90° box, accept the overlap** (decided
   2026-07-26, user). Both clients size the tapped footprint from the 90° swap
   (desktop `PlayArea` row packing; mobile `MatchScreen:421` hover-preview
   offsets and field width math). At a shallow angle the drawn bounding box is
   *wider than either* the untapped or the 90°-tapped box — worst case
   `w·cosθ + h·sinθ` — so a shallow tilt will let tapped cards overhang their
   neighbours slightly. **That is the intended look**: it is what a real table
   looks like, and it is also the cheap option (zero changes to row packing,
   no repack cascade, no risk of the field re-flowing every time something
   taps). Consequence to watch: the *stacking order* now matters visually where
   it did not before — a tapped card overhanging the one to its right should be
   drawn under it, not over it, or the overlap reads as a glitch rather than as
   a table. Check draw order in both clients before calling the tilt done.
5. **Localization** keys for the new setting label in
   `forge-gui/res/languages/*.properties`.

### Which client first — mobile, but do both eventually

Measured 2026-07-26 rather than assumed. **Neither client is dramatically
easier, but desktop is modestly cheaper** — which is the opposite of the one we
want to prioritize.

| | desktop (Swing) | mobile (libGDX) |
|---|---|---|
| exact-90 geometry to generalize | 1 (`PlayArea.getCardPanel:718`) | 2 (`renderedCardContains:74`, `getTargetingArrowOrigin:560`) |
| tap/untap animation | already generic — `Animation.java:203` scales off the constant | hardcoded `-90` at `:288`, must be fixed |
| mouse-point inverse-rotation | already in tree (`CardPanel:647`, badge hit-test) | none; port the desktop one |
| settings screens to touch | 1 (`VSubmenuPreferences` + controller) | 2 (`SettingsPage`, adventure `SettingsScene`) |

So mobile is roughly **2× desktop's work, not 10×**. And a large slice of the
cost — choosing the value list, writing the inverse-rotate helper,
localization, building and actually playing a game to check it — is paid once
regardless of how many clients ship it. Doing a single client saves maybe a
third of a small job, which is not enough to justify a split experience.

**Prioritize mobile/Adventure**, for reasons that are about *this* work rather
than a guess at upstream's roadmap:

- Item 4 (resizing) is mobile-only, so `forge-gui-mobile*` is the tree already
  being built and played on — one build to compile, one client to test.
- Upstream does invest more there: over the last 12 months `forge-gui-mobile`
  took 430 commits vs `forge-gui-desktop`'s 262 (6-month split: 220 vs 188).
  Real, but note the shape of that number — **desktop is not abandoned**, it is
  simply the slower-moving of two live UIs. Don't plan as if it were dead.
  (`forge-gui-mobile-dev` itself is only 8 commits in 6 months; it is a thin
  launcher over `forge-gui-mobile`, which is where the work lands.)
- Desktop's share is small enough (one hit-test, one settings screen) that it
  can follow later without re-deciding anything.

**Nobody needs to pin a version.** The angle is a local render preference
defaulting to `"90"` — stock behavior for anyone who never opens settings — and
it is never sent over the wire. A table can mix clients and angles freely; each
player sees their own board their own way.

### Acceptance

At 90° the build is visually and behaviorally identical to stock (the step-1
gate). At 60°: tapped cards are legible; clicking a tapped card anywhere on its
drawn face selects it; targeting arrows still anchor to the card; tap and untap
animations start and end at the configured angle; and overhanging tapped cards
are drawn *under* their right-hand neighbours (per the reservation decision
above), so the overlap reads as a table rather than as clipping.

Upstream: the step-1 hit-test generalization stands on its own as a latent
correctness fix and is an easy yes. The preference is bigger and more
opinionated — offer it separately so the first one isn't held hostage to
taste.

---

## 6. Deck-site import on mobile — expose what already ships

Upstream #10570 shipped per-deck URL import (Archidekt/Moxfield) with
edition + collector-number fidelity and a per-deck reload button. **Verified
2026-07-26: the machinery already lives in the shared module** —
`forge-gui/src/main/java/forge/deck/{DeckUrlLoader,DeckUrlProvider,
ArchidektDeckUrlProvider,MoxfieldDeckUrlProvider}.java` — and its *only*
consumer is `forge-gui-desktop/.../deckchooser/FDeckChooser.java`. **Nothing
needs porting; the mobile UI simply never got a button.**

So this is UI wiring in `forge-gui-mobile` (deck chooser / `FDeckEditor` entry
point): a URL field, a call into `DeckUrlLoader`, a save into the local deck
store, and the same reload affordance desktop already has. Probably the highest
value-per-line item on this list for a Commander night — everyone shows up with
an Archidekt link — and it lands in the client item 4 already prioritizes.

Watch: the loader is synchronous, with 15 s connect / 30 s read timeouts
(`DeckUrlLoader:192-196`). Desktop can afford to block a Swing dialog; the
libGDX UI **must not block the GL thread** — run it off-thread with visible
progress, the way the mobile UI already handles the online image fetcher.

---

## 7. Bulk sync: every public deck from a username

Requested 2026-07-26 as *"folder syncing, including syncing all public decks
from a particular user — that avoids any need for auth"*. **Those two halves
behave differently and only one of them avoids auth.**

**Public-decks-by-owner: yes, and it is the right primitive.** Archidekt exposes
an unauthenticated paginated listing —
`https://archidekt.com/api/decks/cards/?owner=<username>&ownerexact=true&orderBy=-createdAt&pageSize=50`.
Community-documented only: Archidekt publishes no API docs (open beta, changes
too frequently to keep them current) and warns that heavy use trips rate
limiters. So treat the endpoint as *unstable*: tolerant parsing, a clear failure
message when the shape changes, and no assumption that it will look the same
next year.

**Folder syncing: no — and it does not buy what it was expected to buy.** No
public folders endpoint surfaced in any search, and folders are a **per-user
organization feature** — precisely the kind of thing that sits behind the
account. Folder sync would therefore *reintroduce* the auth problem rather than
dodge it. The auth-free property comes from the decks being **public**, not from
folders being folders.

The organizing goal is still worth having, and there are two ways to get it with
no folders API at all:

- **Sync into a local Forge folder** — one Forge deck folder per synced
  username. Entirely local, needs no remote concept, and is probably what
  "folder syncing" means operationally anyway. Layout decided below.
- **Filter client-side on grouping the payload already carries.** Check at
  implementation time whether the owner-listing JSON exposes a
  folder/category/tag per deck; if it does, folder filtering falls out for free.
  Verify it, don't assume it.

### Where synced decks land

Imported decks do **not** go into Forge's format-partitioned stores. They live
in their own flat collection — `DeckUrlLoader.getStorage():150` builds a
`StorageImmediatelySerialized<Deck>("URL decks", …)` rooted at
`DECK_BASE_DIR + "URL"`. So the layout inside `decks/URL/` is entirely ours to
choose; nothing in Forge forces a shape.

**Recommendation: `decks/URL/<username>/`, flat, with format as deck metadata —
not a folder level.** Two reasons:

- **The format axis already exists twice in the UI.** `FDeckChooser` is
  constructed per `GameType` (`:75` — `isForCommander ? Commander :
  Constructed`) and drives layout off `getGameType().getDeckFormat()`
  (`:145/190/206`), so when you are picking for Commander night the chooser is
  *already* Commander-scoped; and the URL pool is handed to an `ItemManager`
  (`:302`, `NET_DECKS` config) that brings its own filter/search UI. A
  `<format>/` folder level re-encodes in the filesystem a dimension the UI
  already has — and on a Commander night it degenerates into chains of
  single-child folders (`alice/Commander/deck.dck`) for essentially every deck.
- **Re-sync must never move a deck.** Any layout that adapts to what a user
  currently owns — "flat until they have two formats, then split" — relocates
  existing decks the first time a friend uploads a Modern list. That breaks
  muscle memory and any last-used/favourite pointer. A stable path is worth more
  than a tidy one for something that re-runs.

  **Mobile checked 2026-07-26 — the argument holds there too, so this is
  decided, not deferred.** The libGDX chooser is game-type scoped exactly like
  desktop: `FDeckChooser.promptForDeck(title, GameType, forAi, callback):90`,
  constructor `FDeckChooser(GameType, isAi, handler):126`, and
  `lstDecks.getGameType()` drives its behaviour throughout. Decks go into a
  `DeckManager` `ItemManager`, which carries filter/search like the desktop one.

  One narrower question stays open and is **not** a layout question: whether the
  URL-deck list *hides* format-illegal decks or merely shows them. Item 6 will
  answer it concretely when the mobile screen gets wired. Note that **a folder
  layout would not fix it either** — if the picker doesn't filter, folders just
  convert scrolling into navigating. Filtering is the right lever regardless,
  and it is independent of where the files sit. So: flat layout, and if the list
  turns out not to filter, add the filter.

Provider is recorded as deck metadata rather than a path level (`archidekt:` /
`moxfield:` source keys already exist — `DeckUrlLoader:156-167`). Only
disambiguate in the folder name if the same handle is synced from two sites.

### The "unknown format" bucket — the prerequisite nobody would notice

**There is no unknown-format state today: both providers already collapse it to
`Constructed`, silently.** Archidekt maps four numeric cases and defaults the
rest (`ArchidektDeckUrlProvider:127-137` — 3/11/12 → Commander, 6 → Pauper,
13 → Brawl, `default -> Constructed`); Moxfield calls
`DeckFormat.smartValueOf(value, Constructed)` and catches the
`IllegalArgumentException` to return `Constructed` anyway
(`DeckUrlLoader:142-148`). So an Oathbreaker list, a Canadian Highlander pile,
or a deck with no format set is *already* filed as Constructed — and looks
exactly like a real Constructed deck.

**So the prerequisite for any "invalid/unsorted" bucket is to stop destroying
the label at the provider boundary**: preserve the site's raw format string
alongside the mapped `DeckFormat` (or add an explicit `Unknown` sentinel) so
downstream can tell *"genuinely Constructed"* from *"we had no idea"*. Small,
precise, and load-bearing — nothing else here works without it.

**Then route on one failure mode only, and annotate the other two.** Three
distinct things get conflated by the word "invalid", and they want different
handling:

| | what it is | handling |
|---|---|---|
| (a) site format unmapped or absent | a **routing** problem — we don't know where it goes | **route** it: an `Unsorted` folder |
| (b) format known, deck doesn't conform | `DeckFormat.getDeckConformanceProblem()` already returns a human-readable reason (size, singleton, illegal commander) | **annotate**, don't move |
| (c) cards Forge can't resolve | unscripted card or uninstalled set — the most common real failure for a stranger's deck | **annotate**, don't move |

Call the bucket **`Unsorted`, not `Invalid`** — in case (a) the deck is fine, we
simply couldn't place it, and a name that blames the deck will send people
hunting for a defect that isn't there.

Cases (b) and (c) should never relocate a deck. It is still your friend's deck
and they will want to *fix* it, not find it in quarantine — and a deck that
becomes legal later (a card gets scripted, a set gets installed) would have to
move back, which is the same re-sync instability the flat layout is chosen to
avoid.

**Moxfield: build the seam, defer the provider.** Its per-deck public endpoint
(already in use) keeps working, but bulk listing sits behind a **whitelisted
User-Agent issued by Moxfield support, plus Cloudflare bot protection** — with a
documented open issue (Nov 2025) where even whitelisted agents still hit
Cloudflare/reCAPTCHA. That is a relationship problem with an unresolved failure
mode, not an engineering one. Ship Archidekt bulk behind a provider-agnostic
interface, leave Moxfield bulk unimplemented, and pursue the whitelist only if
someone actually asks. Do not let it gate the feature.

**Politeness is mandatory here in a way per-deck import never was.**
`DeckUrlLoader` has no throttling at all today — correct for one deck on a
button press, wrong for N+1 requests against a service that explicitly warns
about rate limiters. Reuse the norm this project already set in the DC pool
fetcher: sequential requests, **≥2 s apart**, a hard cap on decks per sync,
honest progress, and a User-Agent that identifies the client (the existing
`"Forge Deck URL Loader"` string is the right shape; make it name our fork if we
ship our own builds).

**Reuse over rebuild:** enumerate ids, then hand each one to the *existing*
per-deck provider path, which already handles sections, editions, collector
numbers and naming. Bulk sync should be a loop and a folder, not a second
importer — and #10570's per-deck reload button means per-deck re-sync semantics
already exist to build on.

Upstream: this is the exact "remaining gap" the upstream worklist identified on
07-18, so it is a plausible contribution — but it is larger and more
etiquette-sensitive than items 4–6. Item 6 is the easier, more obviously-wanted
half of the same gap. Offer 6 first.

---

## Branch hygiene while the security work is in flight

As of 2026-07-26 the separately-tracked workstream referenced in the footer note
below is live and is landing commits on the `playable` branch family. Its
contents stay out of this file; what matters here is only the coordination
rule.

The QoL items in this doc touch UI files exclusively (`forge-gui-mobile*`,
`forge-gui-desktop/view/arcane`, `ForgePreferences`, language props) and do not
overlap the other workstream's files at all — so the two can proceed in
parallel. Branch *ownership* still needs care.

**Do not check out `playable` in a worktree.** A branch can live in exactly one
worktree, so claiming it would block the other workstream from committing to
it. Cut a new branch from its tip instead — **done 2026-07-26**:

```
git worktree add -b playable-qol ../forge-play playable
```

`playable-qol` @ `cc32912078` in `../forge-play` is where all QoL code for
items 1–5 goes. `playable` itself remains unclaimed by any worktree.

The Anvil-side docs (this file, the project map, the Status section) stay on
`main` rather than moving to a side branch: they are the public record of the
track, they collide with nothing, and fragmenting them across branches costs
more than it saves. Only the *code* needed its own branch.

Merge `playable-qol` back once the other workstream's commits have settled (or
rebase onto `playable` if it moves first). Same rule on the Anvil side: `main`
and the notes branch
(`security/playable-multiplayer`) share a single worktree — keep the tree clean
and commit promptly so a branch switch is never blocked.

---

## Adjacent items tracked elsewhere (swept 2026-07-26)

A sweep of `docs/design/`, `docs/devlog/` and `docs/decisions/` for QoL markers
turned up nothing else player-facing that belongs *in* this file, but three
things sit next to it and should not be re-derived from scratch:

1. **Asset-update delta — the upstream twin of item 2.**
   [upstream-worklist.md](upstream-worklist.md) "Queued idea — Android
   incremental asset updates" (2026-07-18) carries archaeology item 2 lacks: no
   recorded upstream discussion of why deltas don't exist (the
   `AssetsDownloader` history iterates endlessly on *prompting/versioning*, never
   on *transfer granularity*); a zero-hosting-change variant — **HTTP Range
   requests into `assets.zip`**, diffing entry CRCs against local files, with a
   full-download fallback when the server ignores Range; and a Discord
   cross-check confirming no prior art. Two traps recorded there: **"delta"
   collides with netplay delta patching** in that community (reportedly
   troublesome — avoid the term when pitching), and the
   mandatory-download-on-build-mismatch semantics must be preserved, since res
   and engine are one pinned unit (the same invariant as our own fork
   discipline). Fold both into item 2 when it is picked up.

2. **Deck-site sync — GRADUATED into this file (2026-07-26, user).** Was queued
   in [upstream-worklist.md](upstream-worklist.md) since 07-18; now split into
   **item 6** (mobile exposure) and **item 7** (bulk sync by username) above.
   The upstream entry remains the pitch-side record; keep the two in sync as
   with item 5.

3. **The UI-platform lean is already recorded** —
   [collection-mode-sketch.md](collection-mode-sketch.md), 2026-07-18. It
   reached today's mobile-first conclusion by *different* evidence (no large UI
   modernization program upstream; desktop Swing gets maintenance and small QoL;
   platform investment flows to libGDX — iOS support PR #11190, Adventure
   feature PRs), and its standing lean is to build Chronicle's UI on the libGDX
   frontend. Today's commit-count read corroborates it; treat item 5's
   mobile-first ordering as consistent with that lean rather than as a new
   decision.

Not player-facing, checked and excluded: `m3-candidates.md` Track D
"Infrastructure QoL" is research-side only (VRAM elasticity, monitor/babysit
polish — all landed). Also not swept, deliberately: the separately-tracked
workstream's notes branch.

---

## Suggested sequence

Two independent tracks. The **QoL track (4 → 6 → 5 → 7)** is what Commander
night actually feels; the **updater track (3 → 2 → 1)** only matters once we are
shipping builds to other people's machines.

1. **Item 4 tier T1** — one-line unlock plus a small `resize()` fix, and it is
   the change a player notices within ten seconds. Best first commit on the
   branch: small, self-contained, immediately testable.
2. **Item 6** — mobile deck-site import. Pure UI wiring over machinery that
   already ships in the shared module, and the thing everyone actually does on
   game night (paste a link). Highest value per line on the list.
3. **Item 5 step 1** (hit-test generalization at an unchanged 90°) — a no-op
   refactor whose correctness gate is "nothing changed", so it is safe to land
   before anyone has decided on a favourite angle. Steps 2–5 follow whenever
   the taste question is settled.
4. **Item 7** — bulk sync by username. Bigger, network-etiquette-sensitive, and
   strictly more useful once item 6 exists to display the results. Archidekt
   only; Moxfield stays a stub.
5. **Item 3** — trivial, and required before any of our own builds can
   self-update at all.
6. **Item 2 → 1** together — a delta payload makes seamless in-place apply
   cheap.
7. **Item 4 tiers T2/T3** — only if T1's fixed-scale compromise actually annoys
   someone in play. Do not pre-pay for it.

Still none of it scheduled; revisit when the Commander-night plan firms up.

> A further workstream — multiplayer protocol hardening — is tracked separately
> and is **not** in this file. See the local-only note on branch
> `security/playable-multiplayer` (held back from this public repo pending
> private upstream disclosure).
