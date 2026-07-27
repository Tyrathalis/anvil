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

## Suggested sequence

1. **Item 3** — trivial, and required before any of our own builds can
   self-update at all.
2. **Item 2 → 1** together — delta payload makes seamless in-place apply cheap.

None scheduled; revisit when the Commander-night plan firms up.
