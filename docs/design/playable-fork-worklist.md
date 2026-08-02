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

**L2b — the sprite batches carry a projection fixed at construction.**
*Found by testing on 2026-07-26, not by the original read of the code — L1+L2
alone are **not** sufficient and the first build of T1 was visibly broken.*
`Graphics.java:38-39` holds `new SpriteBatch()` and `new ShapeRenderer()`;
libGDX builds each one's ortho projection from `Gdx.graphics` in the
constructor and never revisits it. `Graphics.begin()` (`:94`) only sets logical
bounds — it never touches the projection or calls `glViewport`. So with L1+L2
applied, a window launched at 1280×720 and dragged to 1720×1382 still drew the
UI at 1280×720 **anchored to the GL origin in the bottom-left**, rest of the
window black. `Forge.animationBatch` (`Forge.java:191`) is a third such batch.
Fix: a `Graphics.resize()` that re-orthos both, called from `Forge.resize()`.
Safe between frames — the transform stack rides on the *transform* matrix
(`Dtransforms` / `batch.getTransformMatrix()`), not the projection one.
Corroborating evidence that this was always the intended-but-unfinished shape:
`FrameRate.resize(int,int)` (`FrameRate.java:36`) already existed and **was
never called from anywhere**.

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
  `setWindowSizeLimits(minW, minH, -1, -1)` for a sane floor, update
  `screenWidth`/`screenHeight` inside `Forge.resize()` before forwarding, **and
  re-project the batches (L2b)**. Leaves L3 alone: fonts and touch targets stay
  at launch scale, which reads fine within roughly ±40% of the launch size and
  visibly off beyond it. **This is the tier that unlocks compositor snapping.**
  Ship it first and play a real game on it before deciding whether T2 is wanted.
  **BUILT 2026-07-26** on `playable-qol` (`41cb5f5bc9` L1+L2, `61088aff57` L2b) —
  see the verification note below for what is and isn't confirmed.
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

**Backend question answered 2026-07-26: there is only one arm to test here.**
The box is a Wayland/KWin session (`XDG_SESSION_TYPE=wayland`), but the
launcher pulls LWJGL **3.3.3**, whose `lwjgl-glfw` artifact ships no
`natives-linux-wayland` classifier — only `natives-linux` (X11). So the app
gets the **X11 GLFW native via XWayland**. KWin applies X11 size hints to
XWayland clients the same way it does to native X11 ones, so the T1 mechanism
holds; native Wayland is not reachable without an LWJGL bump and is therefore
not a testable arm on this build.

**Verified 2026-07-26 (automated, `xprop` + window captures):**

- **The mechanism, objectively.** With T1 applied the window publishes
  `WM_NORMAL_HINTS: program specified minimum size: 480 by 320` **and no
  maximum size hint**. That is exactly the difference that matters —
  `setResizable(false)` published max == min, the fixed-size advertisement that
  makes KWin decline to tile at all.
- **Live viewport.** Launched 1280×720, resized to 1720×1382: pre-L2b the UI
  drew at 1280×720 in the bottom-left with the rest black; post-L2b the UI fills
  the window. Clean startup logs both runs.

**Human pass 2026-07-27 (user): resizing and edge-snapping confirmed working
in real use** — the two things automation could not claim (an actual drag to a
screen edge with KWin offering the tile) are now verified. Remaining acceptance
residue: a *full match* at half-screen/maximized hasn't been specifically
reported; expect it to be covered incidentally the next time a game is played
on this build.

**Pre-existing quirk, not caused by T1 and not fixed by it:** the boot
mode-selector (`SplashScreen.java`) has an **empty `doLayout(width, height)`
(`:65-66`)** and positions its two buttons bespoke inside `draw()`, so on resize
the logo re-centres off live `getHeight()` while the buttons keep launch-time
positions and can overlap it. Ordinary screens are unaffected — they implement
`doLayout`, and `FContainer.setSize()` (`:96-100`) calls it. Only reachable by
resizing during the two seconds you are on the selector. Left alone.

> **FIXED 2026-07-27 (`playable-qol` `4ad8b4c94b`).** "Left alone" didn't
> survive contact: with the resizable window the launch-time restore made the
> overlap show up on *every* boot (user hit it twice). Bounds math moved into
> `layoutSelectorButtons()`, called from the previously-empty `doLayout` and at
> button creation; skipped while the exit animation slides the buttons.

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

   **Step 1 LANDED for mobile 2026-07-27 (session 2; `playable-qol`
   `d3bd019dc6`/`d52a43e6aa`/`514efc0dc7`).** How the open decisions resolved:

   - **One shared helper, not one per client:** `forge.util.RotatedRect` in
     `forge-gui` — pure `java.lang`, no libGDX/Swing, no `Utils` class-init
     landmine. `forge-gui-mobile` got **no test infra**; the geometry test
     (`RotatedRectTest`, TestNG) lives in `forge-gui-desktop`'s existing tree,
     which depends on `forge-gui`. Desktop's own step reuses the same class
     (convention note: helper angle = the mobile `startRotateTransform`
     convention; Swing callers pass the *negated* `Graphics2D.rotate` angle in
     degrees — both clients' stock tap is −90 in it).
   - **The identity gate ran and is strict where it matters:** hit-test
     bit-identical to the legacy swap box at −90 over dense grids (~60M
     points, 4 geometries, zero mismatches; trig snapped exactly at multiples
     of 90). The *bounding box* (arrow anchor only) is identical to ~1e-5 —
     call-site float pivot rounding, asserted at that tolerance.
   - **Latent bug found by the derivation, fixed by the same technique:** on
     **180-rotated fields** (local two-human, non-hotseat matches — the
     Commander-night mode) `CardAreaPanel.draw` composes an outer 180°
     rotation with the +90 tap, but the old angle-blind hit-test kept the −90
     box: **the drawn tapped card sits offset by h−w from where taps were
     accepted** (top ~40% of the card missed; empty space below it hit).
     Fixed by undoing the outer 180 (point reflection about the untapped rect
     center) before the base test; targeting-arrow anchors had the same
     offset and now key off the drawn box. Untapped cards are
     reflection-symmetric ⇒ unchanged in every mode. **Formula-verified in
     the unit test; owes a human pass in a real local two-human match**
     (untestable single-handed, same XTEST wall as items 4/6).
   - **Arrow origin generalized now rather than at step 2** (it needed the
     same bounding-box math); the `:288` untap-animation hardcode stays step
     2 as planned. **Desktop `PlayArea.getCardPanel` still open** — small,
     precedented, next round with the same helper.

   **Steps 2, 3 and the desktop hit-test ALL LANDED 2026-07-27 (same
   session, continued; `playable-qol` `484fdb3df5`/`ac824cc606`/`33d8c64b41`)
   — item 5 is now BUILT end-to-end on both clients.**

   - **Step 2:** `CardUnTapAnimation` sweeps from `getTappedAngle()` — the
     `:288` hardcode is gone (it was also wrong on 180-rotated fields, where
     the untap swept from the wrong side).
   - **Desktop hit-test:** `PlayArea.getCardPanel` inverse-rotates via a new
     `RotatedRect.inverseRotate` (returns the local point so the caller keeps
     its exclusive-bounds comparisons where mobile's are inclusive). New
     desktop-form identity test: full integer pixel grids, zero mismatches.
     `isBadgeHit` already inverse-rotated and needed nothing.
   - **Step 3, the pref:** `FPref.UI_TAP_ANGLE`, default `"90"`, values
     **90/75/60/45/30/15** (30/15 added same day — play feedback: 45 was not shallow enough; `255df64491`), localized in all nine languages. Mobile caches it in
     `Forge.tapAngle` (the `animatedCardTapUntap` pattern) with a defensive
     parse (fallback outside (0, 90]); exposed in `SettingsPage` **and** the
     adventure `SettingsScene`. Desktop: `CardPanel.TAPPED_ANGLE` became a
     lazily-read value — **degrees are the source of truth** (exact multiples
     of 90 keep the snapped hit-test math exact; radians derived for
     paint/animation); the `PlayArea` in-flight guards read the same accessor;
     combo in Graphic Options refreshes the cache. Full desktop suite 336
     green; shipping jar builds.
   - **Step 4 draw-order check, static half done:** **mobile is correct by
     construction** — `FContainer.draw` iterates children forward, rows add
     left→right, so a tapped card's rightward overhang draws UNDER its right
     neighbour (the table look). **Desktop is inverted**: Swing paints
     lower-index children on top, so at a shallow angle a tapped card would
     overlap OVER its right neighbour. Fixing it means z-order surgery that
     interacts with the deliberate left-on-top stack fanning — assess
     visually when the desktop tilt is actually played, don't engineer blind.
     At the default 90° none of this is reachable.

   **Owed (human/visual):** play at 60° on mobile — legibility, tapping the
   drawn face, arrows, animation endpoints, overhang direction; the
   rotate-180 two-human check from step 1 stands; desktop shallow-angle look
   (incl. the overlap direction above) whenever desktop gets played.

   **Desktop look VERIFIED 2026-07-28 (user, desktop client at 30°): "looks
   about the same as mobile — that one's fine. Overlap looks intentional."
   That also CLOSES the step-4 draw-order question: the inverted Swing
   z-order (overhang over the right neighbour) does not read as clipping in
   practice, so the z-order surgery item never activates.** Item 5's only
   remaining residue is the rotate-180 two-human check.

   **The rotate-180 check RAN 2026-07-28 (user, shared-screen two-human in
   the Adventure-styled build) and found a STOCK RENDERING BUG deeper than
   the hit-test one (`b65a74cc85`, shipped v6):** at 30° the rotated side's
   tapped cards rendered facing the bottom player, mirrored (user: 330 where
   the table look says 210). Root cause is in `Graphics` itself —
   `startRotateTransform` idt()'d the live matrix, so **nested transforms
   never composed**: the tap rotation inside a 180-rotated panel silently
   wiped the outer 180. The stock negation in the rotated-field
   `getTappedAngle` override was a hand-calibration to exactly that breakage
   — bare +θ equals true composition 180−θ **only at θ=90**, which is why
   nobody ever saw it. Fix: transforms now save/restore and compose (the
   `Dtransforms` consumers only ever read the live matrix, so they're
   unaffected), and the negation override is deleted; at 90 the result is
   pixel-identical to stock. Step 1's own rotated-field hit-test modeled the
   *composed* draw all along, so it now matches rendering at every angle.
   Two more observations from the same pass: **the sideways stack showed no
   items** — predicted to be the same nesting bug (children of the rotate-90
   header drew at unrotated coordinates) and expected fixed by v6,
   unverified; **the card zoom popup renders upright on the rotated side** —
   stock behavior (global overlay, outside all panel transforms), noted as
   possible polish, not fixed. **Owed: the user re-runs the two-human pass
   on v6** (tapped-card orientation 210-style at 30°, taps landing on the
   drawn face, stack items visible sideways, animations).

   **v6 VERIFIED 2026-07-28 (user, screenshot): the rotated side's tapped
   cards render the table look at the shallow angle — "looking more
   appropriate."** The rotate-180 check is thereby substantively closed:
   it ran, found the stock nesting bug, and the fix is confirmed in play.
   Incidental residue, expected to self-verify in future two-human games:
   taps on the rotated tapped face (hit-test provably matches the now-fixed
   draw), and stack items in the sideways header when something is actually
   on the stack in that mode.
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

**BUILT 2026-07-26** on `playable-qol` (`db05b25b86`). How it landed, and the
two places the plan above was refined by contact with the code:

- **Why it was absent is now exact.** `DeckType.PROVIDED_DECK_URL` *is* already
  in the shared `DeckType.ConstructedOptions`/`CommanderOptions` arrays
  (`DeckType.java:78/100/113/122`), but the mobile chooser does not read those —
  it builds its combo from a **hand-written `addItem` list**
  (`FDeckChooser.java:545-613`). So the entry was omitted rather than filtered,
  and `refreshDecksList`'s `default:` arm would have hit
  `BugReporter.reportBug("Unsupported deck type")` had it ever been selected.
  Added to the Constructed/Gauntlet, Commander-family and DeckManager lists,
  matching where the shared arrays put it.
- **Entry point: a button, not an inline field** (user decision). "New Deck"
  becomes "Provide Deck URL" for this deck type — the same repurposing the file
  already does to make it "Generate New Deck" for generated types — and it opens
  `FOptionPane.showInputDialog` **pre-filled with the selected deck's
  `getSourceUrl()`**. Re-confirming therefore re-fetches that deck, which is
  desktop's separate reload button folded into the same control rather than
  spending one of only four button slots. Threading uses
  `LoadingOverlay.runBackgroundTask`, which is exactly the show-overlay /
  background-thread / return-to-EDT primitive this needed.
- **Zero new localization keys.** `lblProvideDeckUrl`, `lblDeckUrlLabel`,
  `lblLoadingEllipsis` and `lblUnableToLoadDeckUrl` all already exist **and are
  already translated in all nine locales** — checked. The plan's step-5
  "localization keys" cost is therefore nil for this item (it still applies to
  item 5's new preference).
- **Static sweep clean:** every other `switch` on deck type in the file either
  handles the new value or defaults safely (`getEditorConfig` → Constructed,
  `isGeneratedDeck` → false, `editSelectedDeck` → the duplicate-to-Constructed
  path net decks already use), and `getDeckTypeFromSavedState`'s
  `DeckType.valueOf` round-trips it with an `IllegalArgumentException` fallback.

**Not yet exercised at runtime.** The build compiles and launches, but the
chooser was never opened: **`xdotool` cannot inject pointer input into the app
on this Wayland session** — XTEST pointer warping is refused by the compositor
(`xdotool mousemove` leaves `getmouselocation` at `0,0`), while
`xdotool windowsize` works because that is a window-management request. So the
resize work above could be verified automatically and this could not.
**Human pass 2026-07-27 (user): "the Provide Deck URL folder works great" —
item 6 verified in real use.** Also noted from the same first run of this
instance: the 113 `dc-*` research-pool decks (installed into
`~/.forge/decks/commander/` by `anvil.pool install`) show up in Deck Manager /
the game picker's custom-deck views, since the playable build shares the same
Forge user store the training harness loads from. **User decision: leave them
be.** The one standing caution recorded below in "shared user store".

---

## 7. Bulk sync: every public deck from a username

**BUILT 2026-07-27 (`playable-qol` `96e3d0942a`) — sequence 4→6→5→7 complete;
owes a live sync + play pass.** As-built deltas from the notes below:

- **The recorded endpoint was wrong.** `/api/decks/cards/?owner=…&ownerexact=`
  is a client route ("Client Unavailable" from the API host), established by
  live probe 2026-07-27. The working listing is
  **`/api/decks/v3/?ownerUsername=<name>`** (exact match, paginated via `next`
  which comes back plain-http and needs re-upgrading to https; `pageSize` is
  ignored, ~60/page; `owner=`/`ownerexact=`/`ownerName=` are silently ignored —
  hence a client-side exact-owner re-check on every entry). Parse pinned to a
  captured fixture in `DeckSiteSyncTest` (desktop test tree, 5 tests).
- All the decisions below implemented as decided: `decks/URL/<username>/`
  flat; re-sync overwrites in place keyed on source URL and **never moves**;
  Unknown-format sentinel (unmapped site format id ⇒ no silent Constructed;
  first import lands in `<username>/Unsorted/`, raw id noted in the comment);
  missing-card and conformance problems **annotated in the deck comment,
  never quarantined**; 2s politeness, caps 200 decks / 10 pages; re-syncs
  skip unchanged decks with zero requests via new `Sync Updated At` deck
  metadata (forge-core header/serializer). Moxfield bulk not attempted.
- Mobile UX: the Provide Deck URL button now asks single-URL vs
  "Sync a User's Decks"; sync runs behind the loading overlay, ends with a
  summary dialog (new/updated/unchanged/failed + reasons). The URL store
  gained subfolder listing, so username folders appear in the chooser.
  Desktop chooser exposure not done (same shared core when wanted).
- **First live sync (2026-07-28, user) CRASHED — and the cause was an
  upstream landmine, not the sync logic** (`ad9a9b89c2`, fixed):
  `IStorage.getFolderOrCreate` had never worked in stock Forge —
  `StorageNestedFolders.add` is a TODO stub (mkdir, then throw
  `UnsupportedOperationException`), and `getOrCreateSubfolder` built the
  child unit on the *parent's* serializer, so even without the throw, decks
  would have saved into the parent dir. Item 7 was the first real caller.
  Fixed by routing creation through the load-time nested factory (child
  rooted at the subfolder, with subfolder support of its own — which the
  lazy `Unsorted/` path needs). `StorageSubfolderTest` pins it, validated
  failing first with the production exception. The fixture-pinned sync tests
  couldn't have caught this: they cover parsing, not real on-disk storage —
  the "not verifiable by reading" lesson, third occurrence. Two riders from
  the same crash: `LoadingOverlay.runBackgroundTask` now hides the overlay
  on the task's error path (`14424e2d52` — the crash dialog was unreachable
  behind the modal "Syncing…" overlay), and the storage fix is an
  upstream-PR candidate (latent-correctness class, same shape as the
  hit-test fix). Still owed: a successful live sync + play pass.
- **First successful live sync 2026-07-28 (user), same evening as the crash
  fix: 133 decks in 5–10 minutes — exactly the politeness math** (~136
  requests × ≥2s + fetch latency; under the 200-deck cap). First sync is the
  expensive one by design; re-syncs skip unchanged decks with zero per-deck
  requests. Play feedback drove a same-evening **sync UX round
  (`5dcebd13ff`)**: Enter submits input dialogs (opt-in `FTextField` submit
  handler wired by `FOptionPane.showInputDialog` — the field's edit-mode
  handler was swallowing Enter to close the keyboard; other text fields
  unchanged), the username prompt accepts a pasted Archidekt URL
  (`DeckSiteSyncer.parseUsernameInput`: the `/search/decks?owner=` /
  `ownerUsername=` page usernames actually link to — live-probed, `/u/` and
  `/user/` paths speculatively; unrecognized input passes through verbatim
  so the existing "no decks found" error names it; prompt text updated in
  all nine locales), and the syncer's per-deck progress — already localized,
  previously dropped on mobile (`sync(username, null)`) — now updates the
  overlay caption live ("47/133: Deck Name") via a
  `LoadingOverlay.runBackgroundTask` variant whose task receives a caption
  updater. Remaining residue: play a game with a synced deck.
- **Deletion rider (2026-07-28, user request, `700738bc0f`, shipped v7):
  URL-imported decks were undeletable** — they're read-only snapshots (edit
  = duplicate-to-Constructed), so the editor's delete button was unreachable
  and a bulk sync had no undo (user hit it after syncing a YouTuber's
  decks). Edit Deck on a URL deck now opens an options dialog: **Duplicate**
  (old behavior) / **Delete Deck** / **Delete folder '<user>'** (bulk-synced
  decks only — removes everything the sync created incl. `Unsorted/`, with
  a confirmation noting a re-sync restores from the site). Mechanics:
  proxies carry their folder in `DeckProxy.path` (new path ctor);
  `DeckUrlLoader.deleteFolder` works at the storage level and is pinned by
  a real-directory test in `StorageSubfolderTest`; two new keys ×9 locales.
  Desktop chooser still lacks delete for URL decks (same shared core when
  wanted). Owed: the user deletes the YouTuber folder for real.
  **VERIFIED 2026-07-28 (user): "the mass deletion worked great" — v7's
  folder delete confirmed in real use. Nothing owed on this rider.**

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

  The narrower "does the picker hide format-illegal decks" question is
  **closed** (user, confirmed in code 2026-07-26): Forge runs its own legality
  check when a deck is taken into a game — `FPref.ENFORCE_DECK_LEGALITY`
  (`ForgePreferences.java:205`, **default `"true"`**), consumed at the lobby
  (`forge-gui/.../gamemodes/match/GameLobby.java`) and shared by both clients.
  So the picker only has to *route and label*; conformance has an authoritative,
  default-on gate downstream of it. Label-based exposure in the picker is
  sufficient, and no folder layout was ever going to improve on it — if the
  picker didn't filter, folders would only convert scrolling into navigating.

  This also **retroactively strengthens the "annotate, don't move" rule** for
  non-conforming decks below: quarantining them would duplicate a check Forge
  already performs at the only moment it actually matters.

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

## 8. Horizontal hand zone in the Adventure UI (requested 2026-07-28, user)

Wanted: the Adventure/landscape match UI's hand as a horizontal row (like
portrait mobile) instead of the vertical side panel. **Archaeology done
2026-07-28 — the option already exists in the shared match UI and Adventure
just lost the knob:**

- `FPref.UI_ALT_PLAYERZONETABS` ("Alternate Player Zone Layout (Landscape
  Mode)") is a three-value select — Off / Vertical / **Horizontal** — wired
  through `Forge.setAltZoneTabMode` at boot (`Forge.java:238`, with a legacy
  true/false migration at `:390`) and consumed by
  `VPlayerPanel`/`VCardDisplayArea`/`VField`/`VManaPool`
  (`Forge.isHorizontalTabLayout()`). It applies to every match, Adventure
  included — the pref is global.
- Classic mobile `SettingsPage` exposes it (`:301`, `CustomSelectSetting`).
  **Adventure `SettingsScene:334` has it COMMENTED OUT — as a stale
  `addCheckBox`** from when the pref was a boolean; presumably disabled when
  upstream widened it to three values rather than reworked.
- **Workaround available today, zero code:** set the pref from the classic
  (non-Adventure) settings page — it persists globally and applies in
  Adventure matches after the boot-time read.
- **The implementation task is therefore small:** revive the `SettingsScene`
  entry as a proper three-value selector (the tap-angle work already
  established the multi-value-selector pattern in that scene), not a
  checkbox. Verify visually what Horizontal actually looks like before
  shipping — the mode's exact rendering hasn't been checked, only its
  plumbing.
- **Pairing note: this item is the natural v5 vehicle** — the first release
  after the manifest-path fix, so shipping it doubles as the end-to-end
  in-app delta test.

**BUILT 2026-07-28 same session (`a5e819166a`), published as v5
(`origin/playable` @ `8a04677902`, build stamp 2026-07-29 02:53:10,
production-parse check green).** As planned: three-value combo in the
non-Android branch where the stale comment sat, mirroring the classic
`SettingsPage` wiring (save + `setAltZoneTabMode` + live
`resetPlayerPanels`); initial selection normalizes a legacy boolean pref to
Vertical, matching what Adventure boot forces at runtime in that state.
Owed: the user's visual pass on what Horizontal actually looks like (this
release is also the end-to-end in-app delta test vehicle).

**BOTH VERIFIED 2026-07-28 (user): the v4→v5 in-app update completed
end-to-end — "it downloaded the patch and restarted itself" — closing the
updater track's last owed item; and Horizontal mode works in play.**
Observed limitation, noted not scheduled: the Horizontal zone display covers
only half the bottom width, so it reads cramped on a narrow window — very
reasonable fullscreen on an ultrawide. If narrow-window play matters later,
a follow-up could widen the display area; that is upstream's layout choice,
not something item 8 changed.

## Shared user store: the playable build and the research harness read the same decks

Noticed on the instance's first real run (2026-07-27): Deck Manager shows the
113 `dc-*` decks. Traced end-to-end — they are the research pool, and the
sharing is deeper than cosmetic:

- `anvil.pool install` copies the built pool into
  `~/.forge/decks/commander/` (`anvil/pool/__init__.py:15`), because the
  research worker resolves decks **by name in Forge's standard user deck
  store**: the pool manifest carries bare filenames (`build.py:87`), the
  harness passes them through (`orchestrator.py:121`), and the fork's
  `AnvilRun` resolves them via `SimulateMatch.deckFromCommandLineParameter`
  (`AnvilRun.java:302`).
- The playable build reads (and its deck editor writes) that same store.

**Consequence: editing, renaming, or deleting a `dc-*` deck in the playable
build's GUI would silently change future research game generation.** The
`pool_version` pin covers the manifest, not the installed file contents —
nothing re-verifies them at launch. Playing games *with* the decks is
completely safe; only mutation matters. (User decision 2026-07-27: leave the
decks visible rather than split the profile — a separate
`forge.profile.properties` user-dir for the playable build remains the clean
isolation move if the clutter or the hazard ever starts to matter.)

**Rider BUILT 2026-07-28 (Anvil `89178d7`):** `launch --pool` hash-compares
every manifest deck's installed copy in `~/.forge/decks/commander/` against
its `data/pool/decks/` source, beside the existing jar-hash gate, and aborts
with "re-run `uv run python -m anvil.pool install`" on any mismatch/missing
file (first 10 problems listed). `anvil.pool.verify_installed_decks` +
`test_verify_installed_decks` (pool suite 15 green). The hazard class is now
loud: a GUI edit to a `dc-*` deck stops the next pool launch instead of
silently changing generation.

## Branch hygiene: sharing the `playable` branch family

Another workstream shares the `playable` branch family. Its contents are
tracked separately and stay out of this file; what matters here is only the
coordination rule.

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

`playable-qol` in `../forge-play` is where all QoL code for items 1–5 goes.
`playable` itself remains unclaimed by any worktree. A third branch,
**`playable-pub` in `../forge-pub`** (added 2026-07-28), is the publish
branch: the QoL commits rebased onto the shared pre-workstream base, and the
thing actually pushed to `origin/playable` — see the PUBLISHED note in the
suggested-sequence section. Rebuild it the same way (cherry-pick
`eed3a3e21d..playable-qol`-style ranges) rather than merging, until the other
workstream's commits are public. Cut at `cc32912078`;
**rebased forward onto `playable`'s tip `eed3a3e21d` on 2026-07-26** before the
first QoL commit (a clean fast-forward — the branch had no commits of its own
yet). The other workstream had moved one commit ahead in the meantime, and
since the two touch disjoint files this cost nothing; doing it before writing
code rather than at merge time keeps the eventual merge trivial.

The Anvil-side docs (this file, the project map, the Status section) stay on
`main` rather than moving to a side branch: they are the public record of the
track, they collide with nothing, and fragmenting them across branches costs
more than it saves. Only the *code* needed its own branch.

Merge `playable-qol` back once the other workstream's commits have settled (or
rebase onto `playable` if it moves first). Same rule on the Anvil side: `main`
and the other track's notes branch share a single worktree — keep the tree
clean and commit promptly so a branch switch is never blocked.

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

4. **Multiplayer hardening — [multiplayer-hardening.md](multiplayer-hardening.md)
   (2026-07-30).** Ran alongside this list from 07-26 and is now closed: nine
   findings, four private reports to upstream, **three fixes merged to public
   Forge master**, plus a public chat-anti-spam PR. Two findings were declined
   with reasoning and remain live — the host is not an authoritative referee
   (a modified client can cheat), and a disconnected seat is reclaimable by
   username alone. Both declined patches live on the `playable` distribution
   branch and are ours to keep.

   **Relevant to this list in one concrete way:** those patches were *not* in
   the published build until v7. `origin/playable` carried none of the 13
   security commits, so the next publish was the first release where any of
   this reached the friends' builds — and merging current upstream master into
   it picked up three of the four for free. **Resolved 2026-07-30: v7 was
   published from the consolidated branch — the security work is now in every
   auto-updating client** (see the publish log below).

Not player-facing, checked and excluded: `m3-candidates.md` Track D
"Infrastructure QoL" is research-side only (VRAM elasticity, monitor/babysit
polish — all landed).

---

## Suggested sequence

Two independent tracks. The **QoL track (4 → 6 → 5 → 7)** is what Commander
night actually feels; the **updater track (3 → 2 → 1)** only matters once we are
shipping builds to other people's machines.

> **UPDATER TRACK BUILT 2026-07-27 (`playable-qol` `fc0b546555` + `ecbffd7116`)
> — code complete for all of 3, 2 and 1; what remains is PUBLISHING, a human
> step.** As-built:
>
> - **Item 3:** constants repointed at `Tyrathalis/forge`; commits atom tracks
>   the **playable** branch (not master); wiki link pinned back to upstream
>   (forks don't carry it); same `daily-snapshots` tag name as upstream so no
>   URL shapes changed. Verified live: with no release published the check
>   404s and the app boots normally.
> - **Items 2+1 together, as this file suggested:** each release publishes
>   `manifest.txt` (sha256/size/path over the jar + the whole res tree —
>   ~55K files, ~6MB text). The updater diffs it against the install
>   (size-first, hash-on-match), shows the REAL download size in the prompt,
>   pulls changed `res/` files from **raw.githubusercontent.com at the
>   release's commit** (the res tree IS the repo tree — per-file delta with
>   zero extra hosting; the "Range into assets.zip" variant wasn't needed),
>   hash-verifies everything before touching the install, applies res in
>   place at the splash (before assets load), and swaps the jar via
>   `UpdateApplier` — a helper spawned from the *staged* jar at exit that
>   retries the copy (Windows lock) and relaunches. No Downloads folder, no
>   installer handoff. Any failure → untouched install + legacy full-package
>   fallback.
> - `scripts/release-playable.sh` assembles a release **from the built jar**
>   (version.txt/build.txt extracted from it — can't drift) and prints the
>   `gh release` commands. Validated locally end-to-end minus the network:
>   `DeltaUpdateTest` (5 tests) runs fetch→plan→download→verify→apply over
>   `file://` URLs, including the corrupt-download abort.
>
> **To go live:** commit+push the playable branch, run the script, publish
> with the printed `gh` commands (create the `daily-snapshots` prerelease
> once, then `upload --clobber` per build). First real-network update pass
> owed once a release exists. Non-manifest deletions are deliberately never
> applied (user-modified res files are left alone; stale orphans possible —
> revisit if it ever bites).
>
> **PUBLISHED 2026-07-28.** The other workstream's commits are not yet
> public, so the release was cut from a dedicated publish branch:
> `playable-pub` = the 19 QoL/updater commits cherry-picked onto
> `5fbc2ac98d` (the shared pre-workstream base; conflict-free, zero file
> overlap — verified with `git diff --name-only` on both ranges, and the
> resulting tree differs from `playable-qol` by exactly the other
> workstream's files). Gate re-run on the publish branch: shipping jar
> builds, DeltaUpdate/DeckSiteSync/RotatedRect suites 16/16 green. Pushed as
> **`origin/playable` @ `cf8e71deef`** (the branch name the commits atom
> tracks); `daily-snapshots` prerelease created with
> `forge-playable.jar`/`manifest.txt`/`version.txt`/`build.txt`
> (2.0.14-SNAPSHOT-07.29, 54,654-file manifest). Verified against the real
> network: version/build/manifest URLs serve, `commits/playable.atom` 200s,
> and a raw res fetch at the manifest commit hash-matches the manifest.
> **Note the branch split: local `playable` ≠ `origin/playable`** until the
> other workstream's commits become public — then reconcile with a merge
> (disjoint files, trivial). Still owed: the first real **in-app** update
> pass (boot an older install, accept the prompt, confirm delta apply +
> restart) — needs a second release to move *to*, so it lands naturally
> with the next publish.
>
> **Second publish 2026-07-28 same day (`origin/playable` @ `31ce920154`):**
> the bulk-sync crash fix round (see item 7's live-sync note) republished
> via `upload --clobber` — the release script + clobber flow works as
> designed. **The >23h update gate is retired in the same batch**
> (`c97755cef7`): upstream's rule shielded users from same-day full-package
> re-pulls, but the delta updater prices updates exactly, so the shield only
> delayed fixes (it would have hidden this very crash fix from every
> less-than-a-day-old install, including the user's). New rule: prompt on
> any strictly-newer published build; an empty delta plan (identical content
> republished) skips the prompt silently. Installs carrying the *old* gate
> (the first release) won't self-offer this fix — one manual jar re-download,
> then the new gate governs.
>
> **First genuine in-app update attempt (2026-07-28, user, v2 install → v3):
> prompt + changelog fired correctly (the retired gate verified live), but
> the delta plan aborted — the res tree contains
> `res/adventure/common/maps/map/aerie/wastetown..tmx` and the manifest
> path-safety check refused `..` as a *substring*, so EVERY real plan failed
> to the legacy fallback (which cannot succeed for this fork: no installer
> jar is published). Fixed segment-wise (`4f1897779e`), the test now carries
> the real filename; republished as v4. No fixture could have caught it
> (synthetic-safe names only) and the earlier live URL verification bypassed
> `parse` — the standing lesson now reads: **verify the production artifact
> through the production code path**; post-publish routine gains "parse the
> published manifest with the shipped parser." Play residue also closed same
> evening: a game with a synced deck was played (user). Remaining owed on
> the updater: one successful end-to-end in-app delta apply + auto-restart
> (the user's v3-equivalent install → v4).
>
> **CLOSED 2026-07-28 (user): the v4→v5 update ran end-to-end in-app —
> delta downloaded, applied in place, auto-restarted. The updater track
> (items 3+2+1) is now fully built, published, and live-verified.**
>
> **Distribution facts (2026-07-28): the shipped jar is a UNIVERSAL desktop
> jar — macOS included.** The `windows-linux` Maven profile only affects the
> unshipped installer module; the shaded jar bundles libGDX's full desktop
> natives (verified: LWJGL dylibs for macOS x64 AND arm64, incl.
> `libglfw_async` — which `GameLauncher.java:40` already switches to on Macs,
> upstream's standard `-XstartOnFirstThread` dodge). One zip of the install
> folder (jar + res, ~259MB, nothing user-specific — user data lives in
> `~/.forge`) serves Windows/Linux/macOS friends alike; requirement is Java
> 17+, and first boot self-updates so the zip never goes stale. **Mac is
> read-verified only — no Mac on hand; the first mac friend is the runtime
> test** (watch for: startup crash on the glfw_async path, Retina scaling). (One
> systemic lesson banked en route: a fix to the updater cannot ship through
> the updater it fixes — the v2 install's buggy parser rejected v4's
> manifest identically; one manual jar refresh was the unavoidable bridge.)
>
> **v7 published 2026-07-30 — first release from the CONSOLIDATED `playable`**
> (`origin/playable` @ `2900701083` = QoL/updater work + current upstream
> master + the security stack: the 3 upstream-merged advisories arrive
> upstream-side, the #11457 chat limits and both declined patches ride
> fork-side). Version `2.0.14-SNAPSHOT-07.31` (build stamp is UTC), manifest
> 54,727 files; jar grew 69→84 MB from the months of upstream master (new
> editions) the old cherry-pick base didn't carry — clients see the real
> delta size in the prompt, as designed. The branch-split note above is
> retired: local `playable` and `origin/playable` reconciled in the 07-30
> consolidation; `playable-pub` is gone and releases cut from `playable`
> directly. Post-publish routine run in full: published jar sha256 matches
> the manifest entry and the local build; **the published manifest parses
> through the published jar's own `DeltaManifest` via jshell** (54,727
> entries, correct version/commit, a real `wastetown..tmx` entry resolves —
> the v4 lesson's check); raw res fetch at the manifest commit hash-matches;
> `commits/playable.atom` 200s. This publish also ships the multiplayer
> hardening to friends' builds for the first time.
>
> **v7 was DEAD ON ARRIVAL in the field, same day — v8 published 2026-07-30
> (`09974ab3ea`) with the fix + an automatic migration for every deployed
> client.** The first real v7 update attempt (the user's own install)
> aborted: `HTTP 400 for .../res/adventure/Realm of Legends/decks/...` —
> the delta URL builder concatenated paths without percent-encoding, and
> the res tree carries **30K+ paths with spaces** (plus `#` `'` `[` `]`
> `&` `!` unicode and a literal `%`; the `#` would truncate silently as a
> fragment). Every v1–v6 delta happened to touch only URL-safe paths; the
> v7 delta was the first big enough to hit the class. Same shape as the
> v4 `..`-substring incident: a path property the artifact always had,
> unexercised until a real plan touched it. Nothing was half-applied
> anywhere (downloads abort before any apply), so all clients sat safely
> on ≤07.29. Fixes, each pinned by tests (DeltaUpdateTest 10/10, the new
> HTTP end-to-end validated failing-first on the exact field path —
> file:// was too lenient to ever catch this; real HTTP servers reject
> raw spaces like GitHub does): **(1) segment-wise percent-encoding** in
> `DeltaUpdater.encodePath`; **(2) the bridge manifest** — a fix to the
> updater cannot ship through the updater it fixes, so plain entries now
> list ONLY the jar (release asset, URL-safe; the one plan ≤07.29 clients
> can always complete) and the full list rides on `#2 ` lines legacy
> parsers skip as unknown headers while the fixed parser prefers them;
> **(3) res self-heal** — after the jar-only hop the local build EQUALS
> the published one, so the strictly-newer gate would never re-open and
> res/ would silently stay stale under the new jar; on equal builds with
> no sync stamp a size-only diff (no speculative 2GB hash pass; same-size
> content changes self-correct at the next release's hash-verified delta)
> offers to complete the update, and the stamp writes after any
> successful apply. Migration is fully automatic for every deployed and
> future straggler client: hop the jar → restart → self-heal completes
> res with encoded URLs. Pre-publish gate extended: **the bridge manifest
> was parsed with the user's actual shipped 07.29 jar** (plan = 1 entry,
> jar only, zero raw fetches) and with the v8 jar (54,727 entries), and
> the production-built encoded URL for the exact failing path was fetched
> live and hash-matched. Post-publish routine re-run in full on the
> published assets.
>
> **The live two-hop migration RAN and PASSED same evening (user's 07.29
> install): hop 1 jar swap + applier auto-restart clean (journal: old jar
> 18:25:20 → new jar 18:25:30), hop 2 self-heal found the stale res,
> downloaded and applied it, stamp written, install verified fully
> consistent (jar sha = published v8, `res-sync.txt` = published
> build.txt).** One wart: after the res-only apply the app exited without
> reopening (user relaunched manually, everything worked). Root cause is
> STOCK and one layer down from the same defect class: `RestartUtil`
> builds one command *string* for `Runtime.exec(String)`, which tokenizes
> on whitespace and honors no quoting — the quoted java binary never
> exec'd on Linux, and the install path (".../Forge Fork/") splits
> mid-path, failure swallowed inside the shutdown hook. **Stock desktop
> restart likely never relaunched for anyone**; hop 1 worked only because
> our `UpdateApplier` already used a ProcessBuilder argument list.
> **Fixed (`57e345f922`) and published as v9 same night:** rebuilt on
> `ProcessBuilder` + argument list; jar launches derive the path from the
> code source (the one space-safe source), trailing program args
> recovered past the jar filename; unreconstructible commands return
> false instead of relaunching garbage (RestartUtilTest 4 new, suite
> 14/14 with DeltaUpdateTest). Serves both call sites (mobile-dev adapter
> + desktop Swing `restartForge`). With v9 up, friends' hop 2 relaunches
> correctly — the fixed RestartUtil is in the jar they hop to before the
> res pass runs. Upstream candidate queued (stock bug, clean standalone
> patch). Pre-publish legacy gate note: the user's install is v8 now, so
> the ≤07.29-parser check runs against the archived v7 jar (pre-fix
> parser) — entries=1, jar only, on the published v9 manifest.
>
> **v10 published 2026-07-30 (`68f48b77f7`): the resize-layer census gains
> its SIXTH member — HEADERS.** Field report (v9, half-ultrawide tile ≈
> square window): the New Game screen showed a one-item "Constructed" bar
> at the top and no other mode was selectable until the window got wider.
> Root cause: `FScreen.doLayout` picks top-bar vs sidebar from the HOSTED
> screen's `width > height` (the home sidebar takes a `0.35×height` slice
> of the window width), while `MenuHeader` re-derived the mode from the
> global `Forge.isLandscapeMode()` — in the disagreement zone the popup
> menu was painted as a "sidebar" INTO the top header strip, one item
> high. Stock never reached the zone (fixed launch size); T1's resizable
> window made it reachable. Fix: `Header` gains a `sidebarLayout` flag
> recording which layout FScreen actually chose (set by FScreen's
> portrait/top-strip branches and by the headers' own
> `doLandscapeLayout`); `MenuHeader` AND `TabHeader`/`TabPage` key every
> sidebar branch on it instead of the global — which also covers the same
> latent defect in Settings (a TabPageScreen hosted over the home
> backdrop, same window-shape zone, incl. Load Game's menu header) and
> makes bottom tab strips horizontal by construction. Android unchanged
> (there the global and the chosen layout always agree). Full publish
> gates re-run (legacy jar-only parse via archived v7 jar; sha triple
> match). **Owed: the user's runtime pass at the square tile** — New Game
> should show the normal top header with a dropdown menu button, and
> Settings-from-home should lay out sanely at the same width.
>
> **v10 menu fix USER-VERIFIED same evening; first Quest-mode session then
> hit a STOCK quest bug — fixed, v11 published (`692d166633`).** Report: a
> new quest said "make a deck" but the editor offered no cards. The save
> (`~/.forge/quest/saves/Tyrathalis.dat`) showed the whole card pool was
> the automatic snow-basics grant — starter generation contributed ZERO.
> Diagnosis ran the actual generator headlessly (jshell + the desktop jar,
> `GuiDesktop` + `FModel.initialize`, probes against the research pin, the
> playable build, AND the live install's res): every standard
> configuration generates 150–290 cards… until the user supplied their
> exact settings — **BALANCED distribution with ALL SIX colors selected →
> 0 cards, silently** (any five → 244). Cause:
> `BoosterUtils.populateBalancedFilters` uses the NON-selected colors as
> the repetition multiplier for preferred-color filters; all-colors ⇒
> `otherColors` empty ⇒ zero filters ⇒ `generateCards` picks nothing and
> runs out of misses without a word. Stock, both clients, any world; the
> save also confirmed the (stock) UX trap that a world with its own format
> (Random Commander) silently overrides the whole starting-pool section.
> Fix: floor the multiplier at one pass; `QuestStartingPoolTest` rides
> `AITest`'s card-DB init (all-colors validated failing-first + two
> controls, 3/3 green post-fix). Upstream candidate queued. Diagnostic
> lesson banked: the journal's `QuestDataIO` reflective-mutation warning
> is the LOAD path — it dated the quest to an earlier session and kept the
> hunt honest. Boosters-count-0 (silent empty pool) noted as an adjacent
> unguarded input, not yet fixed.
>
> **v12 published 2026-08-01 (`af21a8a423`, version `2.0.14-SNAPSHOT-08.02`):
> upstream refresh + the ItemManager context-menu embedded-screen offset
> fix.** Contents: clean merge of 24 upstream commits (HOB/HOC editions,
> card fixes, an AI Room fix — zero conflicts), the Chronicle provenance
> UI (`fedfea5126`), and the context-menu fix (`10c22003df`: menus
> anchored on global screenPos but positioned container-local — off by
> the nav-sidebar width in mobile-dev's desktop shell; stock latent,
> identity on phones, upstream candidate; diagnosed by an instrumented
> second instance on an isolated `-Duser.home` profile driven via
> xdotool). Gate: full desktop suite 419 green post-merge. Manifest
> 54,800 files. Post-publish routine run in full: published jar sha256 =
> local build = manifest entry; manifest parses through the published
> jar's own `DeltaManifest` via jshell (54,800 entries, correct
> version/commit, `wastetown..tmx` resolves); spaced-path res fetch at
> the manifest commit hash-matches; `commits/playable.atom` 200.
> **Publish incident, harmless but instructive: the first upload went at
> CARD-FORGE's `daily-snapshots`** — this clone's gh default repo is
> upstream (for PR work) and upstream uses the same release tag and even
> the same `build.txt`/`version.txt` asset names; only the account's
> lack of write access stopped it (asset-delete 404, nothing landed,
> verified by asset timestamps/uploaders). The release script now prints
> `-R Tyrathalis/forge` on both publish commands with a warning
> (`bd6eb87ada`), and the hazard is banked in session memory.
>
> **v13 published same night (`318953018e`, build 08-02 03:34Z, jar-only
> delta): the updater gains an ORPHAN-DELETION pass — the leave-extras-
> alone policy falsified.** Rebuilding the friend zip from the user's
> field install surfaced three orphans from upstream renames (the
> updater never deleted), one dangerous: a stale
> `The Hobbit Commander.txt` still claiming `Code=HOC` against the
> current `The Hobbit Eternal.txt` — duplicate set codes make edition
> load a coin flip, and EVERY deployed client that updated across the
> rename carries it. `DeltaUpdater.deleteOrphanedResFiles` runs after a
> successful `applyResFiles` (best-effort, logs, never throws); the
> manifest's complete res list makes absence authoritative. Guards make
> mass deletion structurally impossible: a manifest without a
> substantial res list (the legacy jar-only bridge view — driving
> deletion off it would empty the install) never deletes; orphan counts
> over 500 delete nothing; case-insensitive matches of manifest entries
> are skipped (after a case-only rename on a case-insensitive
> filesystem they ARE the manifest file); emptied dirs pruned up to,
> never including, res root. Deletion test validated failing-first
> against a stub; guard tests pin floor/cap/case/missing-root.
> DeltaUpdateTest 15/15, suite 424 green. Post-publish routine in full.
> **Deployment mechanics: cleanup runs in the jar APPLYING an update,
> so clients purge orphans on their first update applied by a v13+ jar
> — i.e. the next content snapshot.** The user's own install was
> hand-cleaned during the zip rebuild (folder verified bit-exact vs the
> v12 manifest via the shipped jar's own diff, then the three orphans
> removed); the distribution zip ships clean and first-boot self-update
> keeps it current, so it need not be recut for v13.
>
> **v14 published 2026-08-02 (`881207ed27`): net-lobby fixes found live in a
> four-player game night — per-keystroke CHANGE events and the team-selection
> echo.** Symptoms: teams unarrangeable (any change cascaded until the lobby
> converged onto one team), chat split into one message per letter, and
> reversed text while typing a name. Two independent causes, one release:
> (1) upstream `76eaaa010e` (iOS fixes, #11190 — arrived via v12's refresh)
> made `FTextField` fire CHANGE per keystroke for live search filtering;
> consumers that treat CHANGE as a committed value broke — online chat sends
> a MessageEvent per event (and clears the field, hence exactly one letter
> per message), the lobby name field commits + broadcasts full slot state
> per keystroke, and each echo `setText` resets the caret to 0 (reversed
> typing). Now gated behind opt-in `setLiveChangeEvents`; no caller opts in,
> restoring pre-#11190 semantics. (2) STOCK team echo, exposed the first
> time 2v2 was attempted: `FComboBox` fires its changed handler on
> programmatic sets, so a broadcast team change re-enters
> `teamChangedHandler` on every other client for a panel it doesn't own;
> the wire listener drops the panel index and the hardened server applies
> client events to the sender's own slot ⇒ the echo rewrites the echoing
> client's OWN team. Guards: handler ignores `!mayEdit` panels and the
> network-apply path; `setPlayerName` skips fields mid-edit. Diagnosed from
> the host journal: chat rate limiter (hardening, #11457) visibly dropping
> the sender-side flood; single-character events on the wire. Checkstyle
> validate clean (run post-push — CI would have gated regardless). Upstream
> candidates queued: the FTextField live-CHANGE regression (upstream chat
> is per-keystroke broken on master today) and the team-echo guard.
> Same-day note: the friend zip's `Forge.command` instructions were updated
> for macOS Sequoia/Tahoe (right-click→Open is gone; Settings→Privacy &
> Security→Open Anyway, or `xattr -dr com.apple.quarantine`), and the JRE
> guidance for friends is pinned: Temurin 21 JRE via
> `api.adoptium.net/v3/installer/latest/21/ga/<os>/<arch>/jre/hotspot/normal/eclipse`.

1. **Item 4 tier T1** — ~~one-line unlock plus a small `resize()` fix~~ — **DONE
   2026-07-26** (`41cb5f5bc9` + `61088aff57`). The "small `resize()` fix"
   estimate was wrong by one layer: L1+L2 alone shipped a visibly broken window
   and the batch re-projection (L2b) was only found by running it. Lesson worth
   carrying into item 5: *these UI items are cheap to write and are not
   verifiable by reading.*
2. **Item 6** — mobile deck-site import. **DONE 2026-07-26** (`db05b25b86`),
   pending a human runtime pass. Pure UI wiring over machinery that already
   ships in the shared module, and the thing everyone actually does on game
   night (paste a link). Highest value per line on the list.
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

**Ordering agreed by the user 2026-07-26.** Still not a scheduled milestone, but
it now has a rough horizon rather than none: Commander night ran on 2026-07-26,
so the next one is roughly **1–2 weeks out**. That is comfortably enough room
for the sequence above in order — the earlier worry about pulling items 1–2
forward (the two the user has now hit twice in real play) does not apply at this
distance. Nothing here displaces M3 closeout or the Grindstone/M4 session.
