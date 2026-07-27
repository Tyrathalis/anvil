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
lives in UI / net-transport / auto-updater code** (`forge-gui`,
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
3. **Add the preference.** `FPref.UI_TAPPED_CARD_ANGLE` in
   `ForgePreferences.java`, default `"90"` so stock behavior is preserved for
   anyone who doesn't touch it. Rendered as a `CustomSelectSetting` in mobile
   `SettingsPage.java` (+ adventure `SettingsScene.java`, which mirrors a subset
   of the same prefs) and as an `FComboBoxPanel<String>` in desktop
   `VSubmenuPreferences` / `CSubmenuPreferences` — both patterns already exist
   in those files. Offer a short value list (**90 / 75 / 60 / 45**) rather than
   a free slider: it bounds the layout-reservation problem below, and neither
   settings screen has a slider widget to reuse.
4. **Decide the layout reservation deliberately.** Both clients size the tapped
   footprint from the 90° swap (desktop `PlayArea` row packing; mobile
   `MatchScreen:421` hover-preview offsets and field width math). At a shallow
   angle the drawn bounding box is *wider than either* the untapped or the
   90°-tapped box — worst case `w·cosθ + h·sinθ`. Either reserve the true
   rotated AABB (more spacing, rows may repack) or keep reserving the 90° box
   and accept mild neighbour overlap. Overlap is probably the better look — it
   is what a paper table looks like — but it must be a decision, not an
   accident.
5. **Localization** keys for the new setting label in
   `forge-gui/res/languages/*.properties`.

### Acceptance

At 90° the build is visually and behaviorally identical to stock (the step-1
gate). At 60°: tapped cards are legible; clicking a tapped card anywhere on its
drawn face selects it **in both clients**; targeting arrows still anchor to the
card; tap and untap animations start and end at the configured angle.

Upstream: the step-1 hit-test generalization stands on its own as a latent
correctness fix and is an easy yes. The preference is bigger and more
opinionated — offer it separately so the first one isn't held hostage to
taste.

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
it. Cut a new branch from its tip instead:

```
git worktree add -b playable-qol ../forge-play playable
```

That reads `playable` without claiming it. Merge `playable-qol` back once the
other workstream's commits have settled (or rebase onto `playable` if it moves
first). Same rule on the Anvil side: `main` and the notes branch
(`security/playable-multiplayer`) share a single worktree — keep the tree clean
and commit promptly so a branch switch is never blocked.

---

## Suggested sequence

Two independent tracks. The **QoL track (4 → 5)** is what Commander night
actually feels; the **updater track (3 → 2 → 1)** only matters once we are
shipping builds to other people's machines.

1. **Item 4 tier T1** — one-line unlock plus a small `resize()` fix, and it is
   the change a player notices within ten seconds. Best first commit on the
   branch: small, self-contained, immediately testable.
2. **Item 5 step 1** (hit-test generalization at an unchanged 90°) — a no-op
   refactor whose correctness gate is "nothing changed", so it is safe to land
   before anyone has decided on a favourite angle. Steps 2–5 follow whenever
   the taste question is settled.
3. **Item 3** — trivial, and required before any of our own builds can
   self-update at all.
4. **Item 2 → 1** together — a delta payload makes seamless in-place apply
   cheap.
5. **Item 4 tiers T2/T3** — only if T1's fixed-scale compromise actually annoys
   someone in play. Do not pre-pay for it.

Still none of it scheduled; revisit when the Commander-night plan firms up.

> A further workstream — multiplayer protocol hardening — is tracked separately
> and is **not** in this file. See the local-only note on branch
> `security/playable-multiplayer` (held back from this public repo pending
> private upstream disclosure).
