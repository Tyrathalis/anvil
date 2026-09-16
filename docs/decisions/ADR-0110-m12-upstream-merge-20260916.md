# ADR-0110: the M12 upstream merge (engine pin `23c3d2a85d` → `97535e047f`) — a merge, not a rebase; the three riders (the probe snapshot, the views flag, the void re-roll skip); the boundary protocol

- **Date:** 2026-09-16
- **Status:** accepted (user, 09-16: "if you think a merge is sufficient here, then I'm fine with a
  merge"; the pin at the tip; the archaeology resized down)
- **Design-doc anchor:** §9 (fork discipline; engine upgrades as dataset boundaries), §6 (search
  as the behavior policy); [m12-plan.md](../design/m12-plan.md) Build order 4 ("the rebase lands
  before it", [ADR-0106](ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md) B, the
  void skip riding it per [ADR-0109](ADR-0109-prelaunch-completeness-audit.md))

## Context

ADR-0106 B placed the upstream sync between evening 5 and Build 4 so the endgame (the post-Build-4
read, the shakedown, the big run, its close) sits in one era against one fresh reference. Build 3
closed 09-16 ([ADR-0108](ADR-0108-m12-build3-closeout.md)); the user asked whether the targets
surface and the throughput work should go ahead of the sync (no: the targets surface lands on the
census controller, the layer the sync conflicts on most, and its pool + read double as the new
jar's first real runs; the allocation head's first fit is Python on existing rows and runs
alongside), then asked for the upstream patches to be read before pinning.

**The survey** (upstream `23c3d2a85d`, 08-22 → `97535e047f`, 09-16 10:36; the full read in the
09-16 session-2 devlog):

- 283 commits (223 non-merge), 820 files; ≈ 45 engine / AI commits, the rest Adventure mode,
  localization, editions, 171 new card scripts. **The controller API is unchanged** — the
  `PlayerController` + `PlayerControllerAi` diff is one storage-land hunk. Two real conflicts
  (`ComputerUtilMana`: our mana-source memo vs the AiCardMemory refactor #11667;
  `AiBlockController`: talor's block-legality cache vs #11790); the rest additive.
- **#11916 and #11925 (khaliostr, Manabrew) are merged upstream** (09-14, 09-16) — we had queued
  #11916 for the sync as a pending PR; nothing to carry.
- **Four changes touch our own decisions.** (1) **#11667** keys the AI memory by a typed
  `MemoryType` and adds `MemorySetMana.UNPAID_COSTS`, written on the test-mode payment path
  (`payManaCost(test=true)`) that `autoPayable` runs inside `quietProbe`, and read by
  `ChangeZoneAi` — the probe's named snapshot list (six card sets) would leak it silently: the
  ≈ 2.7pp class of the 09-09 probe fix reopened. (2) **#11780** is the views lever we dropped
  09-14 as rebase-fragile: `Game.setNoGUIUser()` → `DummyCardView` (the one stub: the ability-text
  refresh), set by `GameCopier` on every copy — search copies get it free. (3) **#11778 = CR
  605.1a**: an activated ability whose cost or effect moves a card to or from a library is no
  longer a mana ability (uses the stack; a priority option, not a payment source) — a format
  change under the invariant; the pool impact is **Chromatic Sphere only** (all 1,701 scripts
  scanned). (4) **#11861** rewrote the AI timeout machinery (`AI_CAN_USE_TIMEOUT` gone, interrupt
  checks, a 2 s join); our bridged priority path overrides above `AiController`, the heuristic
  seats move.
- **What moves the reference:** heuristic changes in blocking (#11790), pump timing (#11739,
  #11742), any-color mana (#11809), storage lands (#11672), reveal effects (#11712), combat
  prediction (#11920, #11925); 8 of 1,701 pool scripts (Hogaak: the no-mana restriction moved to
  a static; Emrakul, the World Anew: protection scope widened; six reveal-flag / AI-hint
  cleanups). Three LKI NPE fixes (#11917, #11683, #11821) may retire part of the copy-crash class.
  #11830 un-skips silently skipped tests. Lazy card loading (#11763) is off by default.
- **Merge vs rebase.** ADR-0025's D4 bump was a true rebase (history rewritten, tag
  `pre-rebase-20260725`); the 08-22 bump at `23c3d2a85d` was a merge. Since then twelve fork tip
  hashes are cited by run headers, ADRs and forkcheck records; a rebase rewrites all of them.

## Decision

1. **A merge, not a rebase.** Tag `pre-merge-20260916` on the fork's `master` (`5e333e9693`);
   the merge of upstream `97535e047f` on the branch `merge-upstream-20260916` (worktree
   `../forge-merge`), fast-forwarded onto `master` once proven. Every pinned tip hash stays
   resolvable. The term "rebase" in ADR-0106 B and the plan was imprecise (user); the sequence
   there stands.
2. **The pin = upstream's tip `97535e047f`** (09-16 10:36; nothing after the last engine commit
   of 09-16 is code). The conflict resolutions: `AiBlockController` = upstream's #11790
   restructure with the fork's `canBlockCached` in place of the direct legality call (the cache's
   three own calls are the only direct ones, as before); `FCollectionTest` = upstream's
   deterministic replacement (#11677). One compile fix: `predictManafromSpellAbility` →
   `predictMana` (renamed in #11667) in `PaymentEnumerator`.
3. **Three riders on the merged jar** (each flag-off byte-identical on the mainline or
   search-copy-only; proven by the new baseline + the flag-on run):
   - **The probe snapshot** (bridged-path only): `AiCardMemory.snapshotAll / restoreAll` (fork-
     local, additive: every entry of the memory map, deep-copied) replace `quietProbe`'s named
     list — a memory set added later is covered without a list. `AiMemorySnapshotTest` asserts
     a named set, an unnamed set and the typed `UNPAID_COSTS` all restore. The game-neutral-probe
     rule's read (autoonly − off on the new jar; 09-09: +0.34 ± 0.48 on 8 divergent games of
     591) is the outcome proof, scheduled with the reference reads.
   - **The views flag** `-Danvil.nogui=on` (default off): `AnvilGames.noGui(game)` marks the
     mainline game right after `Match.createGame()` (before any card exists — `Card`'s
     constructor picks the view class) in `AnvilRun`, `CensusRun` (both sites) and
     `ForkFidelityCheck`. **The proof:** the flag-on forkcheck vs the merged jar's own flag-off
     baseline (same seeds, identical trace hashes); then the default flips and the one-worker
     re-profile prices it (the 09-14 JFR read: the view layer 18–20% of a headless worker).
   - **The void re-roll skip** `-searchvoidskip 0|1` (default 1; header pin `voidskip`): a
     first-ply candidate whose roll-0 copy voided (kind `void`: the forced option absent on the
     copy — a copy-fidelity artifact, deterministic per candidate) is not re-rolled; rolls ≥ 1
     record kind `skip`, value null, calls 0 (the row's arrays keep their length, every reader
     unchanged). 29.6% of first-ply copies on the 09-15 bench cell; ≈ 15% of first-ply copies at
     rolls 2. Search-copy / recording only — the forkcheck cannot see it and does not need to.
4. **The boundary protocol** (ADR-0025 / ADR-0068): (a) the new forkcheck baseline
   `run-20260916-merge-baseline` on the merged jar, flag-off, the standing seed set 20260703+500;
   `compare.py`'s default baseline moves to it; every later tip is proven against it; (b) the
   fork pin moves to the merged tip once the baseline exists and the flag-on run matches it;
   (c) the era-scoped Ante maps are re-fit on the new jar's reference arms (ADR-0036); (d) every
   banked pool (the surface-label pools, the h2 pay pool, the search-row bench cells) is marked
   cross-era and kept as a warm start (ADR-0105 item 5 already treats surface labels as
   policy-conditional, regenerated per era); (e) the day-zero / Build 3 numbers are old-scale
   from here — never compared across the boundary.
5. **The reads on the new jar** (≈ a box day): the heuristic reference read and the `iter-019`
   read (the standard 2,000-game protocol, `final_read.py`), the three-cell g/h read the
   throughput week deferred (24 × 2 on the recipe; the big-run sizing line re-issued from it),
   the probe's divergence read (3d above). **The checks:** the ability-table re-dump + key diff
   (the eight changed pool scripts shift their `ak`; **what a served option whose key is outside
   the table does at serve time is unverified** — checked at the smoke before any served arm);
   the search clock / worker deadline against the new 2 s join; the newly un-skipped fork test
   classes; the copy-crash class census on the baseline (the three LKI NPE fixes).
6. **Sizing:** the archaeology ≈ a day (two conflicts, one rename, the API unchanged) + a box
   day for the baseline and the reads — down from ADR-0106 B's one to three days. Build 4 opens
   on the merged jar with the targets surface as its surface evening (ADR-0109); the allocation
   head's first fit runs alongside on the pre-merge search rows.

## Consequences

- Standing rule born here → [standing-rules.md](../standing-rules.md) (engine hygiene): **an
  engine bump lands as a MERGE with a pre-merge tag, never a rebase** — the fork's tip hashes are
  cited by every run header, ADR and forkcheck record and must stay resolvable; the merge commit
  is the boundary's name.
- The 09-14 "views lever DROPPED" finding is superseded: the layer is upstream-owned now
  (#11780); the lever is re-read under the flag.
- ADR-0104's probe-fix rule gains its mechanism: a probe's snapshot covers the whole memory map,
  not a named list.
- Plan amendments (this commit): Build order 4's "the rebase lands before it" reads "the merge
  (ADR-0110)"; the record entry. CLAUDE.md's state of record moves to the merged tip when the
  baseline lands (addendum here).
- Routed by name: talor's block-legality cache as the first post-launch upstream patch (the
  upstream worklist, 09-16); the mana-source memo as the second; the OOV-key serve path check at
  the smoke; the lazy-card-loading startup timing (opt-in) when the fleet's startup is next
  profiled.

## Addendum 09-16 10:00 — the ability-key drift at the boundary, and the OOV path verified

- The re-dump on the merged jar (`data/runs/merge-boundary/abilities-1db054ade4.jsonl`: 1,701
  cards, 5,149 abilities, 0 missing) vs the pool's table (`abilities-cf2ca6ba.jsonl`, 5,148):
  **5,133 keys stable; 15 gone / 16 added across 12 hosts** — the eight changed pool scripts
  (Atraxa, Dance of the Dead, Emrakul the World Anew ×4, Endurance, Hogaak +2, Orochi Hatchery,
  Sylvan Library) plus four whose canonical text moved under an engine refactor (Entreat the
  Angels, Temporal Mastery, Terminus — the Miracle family — and Ocelot Pride). 0.3% of the table.
- **The OOV path, verified in code** (`anvil/policy/surfaces.py` `AbilityCache.index`): a key
  outside the table returns −1, the caller counts it, and the model keys that option on its host
  row + kind alone — the same path a never-dumped ability play takes today. So the served e3 build
  degrades gracefully on those 16 abilities until the table is extended.
- **Routed:** the table's extension with the 16 new keys through the encoder's ability-table
  command (the pinned LLM embedding; one short job) before the first served arm on the merged
  jar; `data/pool/abilities-<pool>.jsonl` is re-pinned to the merged jar's dump at that step.

## Addendum 09-16 10:12 — the new baseline landed

- `run-20260916-merge-baseline` (the merged jar `1db054ade4`, flag off, seeds 20260703+500):
  500 rows; fork fidelity **451 clean / 48 divergence / 1 outcome mismatch** (the 08-21 baseline:
  450 / 50) — the copier's fidelity is unchanged across the merge. **Against the 08-21 baseline
  332 / 500 main-trace hashes identical** — the boundary's drift (168 games play differently
  under the new heuristic, the eight changed scripts and CR 605.1a); for the record only, never a
  proof. `compare.py`'s default baseline moves to this run (this commit); every later tip is
  proven against it.
- The views-flag proof `run-20260916-merge-nogui` started 10:11 (the same jar, `-Danvil.nogui=on`);
  the reads queue started `merge-ref` at 10:11. The fork pin moves to `1db054ade4` when the proof
  reads identical; the crash-class census on this baseline is read with it.

## Addendum 09-16 11:15 — the views-flag proof PASS, the pin moves, the era's reference number

- **`run-20260916-merge-nogui` (the same jar, `-Danvil.nogui=on`): 499/500 main-trace hashes
  identical to the flag-off baseline; the one miss = 20260969, the standing launch-unstable
  seed (status `divergence` on both sides in both eras, a different hash on every launch — the
  identity-hash residual class); fork fidelity identical (451 / 48 / 1). PASS at the ADR-0025
  standard → the views default flips ON.** The flip tip `8137d0c41c` (views default on,
  `-Danvil.nogui=off` restores; the fork's console modes `anvil` / `forkcheck` / `census` join
  upstream's headless list in `Main.isCommandLineMode` — the silent exit-1-without-DISPLAY
  hazard closed) is committed on the merge branch; its own forkcheck vs the merge baseline heads
  the g/h queue; the three-cell 24 × 2 read then prices the recipe on the merged jar with the
  views lever and the void skip in.
- **The fork pin moves to `1db054ade4`** (the merge `4112a89563` + the riders); `master`
  fast-forwarded to it (285 ahead of origin, unpushed); the worktree `../forge-merge` carries
  the flip tip.
- **`merge-ref` (iter-019 vs the heuristic on the merged jar, 2,000 games, 1,983 decisive, 1
  crash): raw 0.5300 ± 0.0112, Ante-corrected 0.5348 ± 0.0110** — the ckpt of record's number
  in the new era (the old era's 0.5279 ± 0.0110 is not comparable across the boundary; the
  day-zero read's ref 0.538 on the pre-merge jar sat on this scale). The era-scoped Ante maps
  come from these two arms (`ante-merge-refarm-s0/s1`). `merge-heur` (the mirror) running.

## Addendum 09-16 12:05 — the heuristic mirror

- `merge-heur` (no seat bridged, 2 × 1,000 games on the standard pairs + seeds): the two seat
  arms play the SAME games (nothing swaps without a bridged seat), so the read is one population
  of 1,000 games: **980 decided / 19–20 draws / 1 crash (a `NullPointerException` class) per arm;
  seat 0 wins 0.470 ± 0.016** (461 of 980) — a seat-0 / seat-1 asymmetry of the fixed deck-pair
  population, not a symmetry failure (the Build 2 control read's "heur 0.500" was the two seat
  arms' mean, 0.500 by construction). Mean game length 23.2 turns. The era's heuristic
  population for the pool's statistics; the mirror's `arms_report` line reads 0.0000 because no
  seat is Anvil — read the per-seat split from `games.jsonl` as above.

## Addendum 09-16 12:45 — the flip tip proven; the pin moves to `8137d0c41c`

- `run-20260916-merge-flip` (the flip jar `8137d0c41c`: views default ON + the console modes
  headless) vs the merge baseline: **499 / 500 identical, 20260969 the standing seed → PASS.**
  The fork pin = `8137d0c41c`; `master` fast-forwarded to it (unpushed). Every harness game now
  runs with `DummyCardView` (`-Danvil.nogui=off` restores the GUI views).
- The first 24 × 2 recipe cell on that jar: **347 g/h peak / 272 g/h wall (14.1 min, 64 games,
  0 crashes; mean batch 3.9, servers 74% busy)** vs the 09-15 recipe cell's 294 peak / 213 wall
  on the pre-merge jar — the views lever + the void skip + upstream's own perf work, one cell so
  far (the 09-14 rule: three cells decide; cells 2–3 running).

## Addendum 09-16 13:25 — the three-cell g/h read; the boundary closed

- Three 24 × 2 recipe cells on the pinned jar `8137d0c41c` (64 games each, seed bases
  20260917–19, 0 crashes in 192 games): **peak 347 / 353 / 288 g/h → the median 347 g/h; wall
  272 / 166 / 186 (median 186; the wall figure carries each cell's last-game tail and is not the
  read).** The pre-merge recipe cell (09-15, one cell) read 294 peak → **+18% on the merged jar**
  (the views lever + the void skip + upstream's own perf work; not separable at three cells and
  not worth separating). **The big-run sizing line re-issued: the recipe at ≈ 347 g/h ≈ 8.3K
  games/day → 235–350K games in the four-to-six-week envelope** (surface acting on; the
  shakedown's deep arm at its ×2.83 price).
- **The boundary is closed**: the pin `8137d0c41c`, the baseline `run-20260916-merge-baseline`,
  the era's reference (`iter-019` 0.5348 ± 0.0110), the mirror population, the Ante arms for
  the era-scoped maps, the ability-key drift (15 keys; the table's extension routed), the
  allocation head's frozen read (AUC 0.80; ×1.25 whole-game at 90% recall). Every pre-merge number
  is old-scale from here. Next: Build 4 on this jar — the targets surface first (ADR-0109), the
  representation completions, the allocation head's served output; the shakedown after the
  post-Build-4 read.
