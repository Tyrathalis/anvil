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
