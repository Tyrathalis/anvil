# ADR-0026: M3 closeout — strength proven, then re-scaled by the platform it was proven on

- **Date:** 2026-07-28
- **Status:** accepted
- **Design-doc anchor:** m3-plan (all deliverables); closes the milestone opened 2026-07-17

## Summary

M3's four done-when clauses all resolved TRUE, each with its own record:

1. **Veto cause resolved** — ADR-0022 (D1): the "obs gap" was a
   featurization gap (`cmd_tax`, transform v4, zero corpus regeneration),
   and feature + §6c rejected-intent penalty proved to be ONE deliverable
   (run-4 falsified feature-alone; run-5 collapsed first-attempt veto
   0.34→0.0987 vs the 0.1358 bar, post-first-cast commander vetoes −72%
   paired, zero strength cost).
2. **A guarded run beat iter-012 outside noise** — ADR-0023 (D2): the §6f
   full-vis in-loop critic at lr 1e-5 (run-7b) ran 20/20 with zero halts;
   iter-14 read 0.5530 ± 0.0109 corrected, **paired +3.26pp ± 1.16 vs
   iter-012 (t=2.80) — the first outside-noise supersession**. Standing
   recipe: §6d opponent mix + §6c penalty + §6f critic @ lr 1e-5.
3. **The upstream surface landed** — draft PR
   [#11285](https://github.com/Card-Forge/forge/pull/11285) (determinism
   hooks, manabrew co-credited, 3 tests, forkcheck twin 40/40) submitted;
   #11260 design input posted; the #445 protocol review delivered (6-item
   gap list — #445 has since merged with our review as the closing
   comment). Every upstream claim carried a test (the Fireball SVar claim
   was probed and excluded because it did not reproduce).
4. **The rebase is complete** — ADR-0025 (D4): fork onto upstream
   `3e3818f1ba`, #11203 home byte-identical (engine delta now 14 lines in
   two files), `forkcheck -twin` divergence 16.5%→7.0%, `-grpc` BC-ckpt
   twin gate 40/40, fresh baselines recorded, worklist swept.

En route, unplanned but load-bearing: the early-doom ceiling analysis (the
eval ceiling is NOT binding; 531 addressable losses with ranked value-crash
windows = the Grindstone seed list, all on the old scale), the falsified-
lever ledger (feature-alone, τ in [0.3, 1.0], 2× batch — ADR-0024), lr
brackets refined to per-signal-regime and per-batch-size (ADR-0017
extended), VRAM elasticity (task #12), the connive-regression catch and its
method lessons, and the learner-throughput diagnosis and fix (train phase
was 62% of run wall clock at 87% loader wait; collate-in-worker landed as
`c09a755`, 4.7–6.7×, CPU bit-identical gate — see the correction below).

## The honest headline

The milestone's thesis — strength on a community-integrated platform —
resolved with a twist the plan did not predict: **the platform moved under
the measurement.** The rebase (26 `forge-ai` commits of active maintainer
tuning) re-scaled the scoreboard: the RL checkpoint of record fell from
0.5530 to **0.5121 ± 0.0110 corrected — parity with the current
heuristic** — while **RL-over-BC survived robustly (+6.69pp ± 1.55,
t=4.32)**. The core M2/M3 claim (RL produced a genuinely stronger policy
than imitation) holds; the "teacher-surpassing" framing of ADR-0019/0023
was true against the old heuristic and is restated, not re-scaled
(ADR-0025 decision 3). The difference-in-differences that would separate
"heuristic got stronger" from "opponent-specific-fit loss" was underpowered
(−2.45pp ± 2.19) and deliberately not chased.

## Decision

**M3 is CLOSED.** Checkpoints of record: `d6-run7b/iter-014/train/last.pt`
(RL) at 0.5121 corrected on the current engine; `d5-combat/last.pt` (BC)
remains the engine-bump certification policy. **The M4 planning baseline is
0.5121**; every pre-rebase number — including the early-doom ceiling
figures 0.826/0.920 — sits on the old scale.

**Next: the dedicated Grindstone/M4 design session** (fresh context), per
the M1/M2/M3 pattern. Its seed material and standing agenda:

- **Signal source** (the central design decision): ADR-0024 established the
  near-tie residual is *absent signal*, not gradient noise — candidates are
  Grindstone drills (the 531-loss curation list is ready), rollout labels
  under micro-batching (machinery built and parked since M2 D4), and
  post-rebase re-probes of falsified levers.
- **The re-baseline mechanism question**: whether M4 opens with a cheap
  discriminating read (§6d-style opponent-mix decomposition on the new
  engine) or accepts 0.5121 and moves on.
- **Milestone identity**: Grindstone proper vs another split milestone.
- **Old-scale artifacts**: decide which (if any) pre-rebase analyses are
  worth re-running on the new engine before they inform targets.

~~**Hard prerequisite before the next long RL run: the collate refactor.**~~
**Correction (same day, discovered when the closeout session went to build
it): the refactor was already built and gated on 2026-07-26 (`c09a755`, a
parallel session this record had not absorbed).** Worker-side collate at
exactly the learner's seg size (segmentation + padding identical; OOM
elasticity slices the pre-collated segment on dim 0). Measured 0.442→2.062
traj/s at 6 workers (4.7×) / 2.979 at 12 (6.7×); run-7b's 16.6h train phase
projects to ~2.5h, making generation ~80% of a run. Gate note for the
record: GPU bf16 is not bit-reproducible (new-vs-new ≈ old-vs-new ≈ 3e-5),
so the byte-identical gate ran on CPU, where the model is deterministic —
old-vs-new bit-identical across all 195 tensors, new-vs-new as control.
**The next long RL run is unblocked.**

## Consequences and carried-forward inventory

- Every M4 RL run generates on the rebased fork (`master` @ `5fbc2ac98d`);
  pre-rebase runs stay on `pre-rebase-20260725`, no mixing.
- **Upstream watches:** #11285 still open with zero reviews (the queued
  #11360 complementarity comment doubles as the natural review nudge); the
  Copier→Snapshot consolidation follow-up remains maintainer-blessed;
  expect the connive-lines conflict at the next rebase and drop ours.
- **Small fork items:** the MinMaxBlocker illegal-block-discard realizer
  gap (serve-side, pairs with block-drop re-ask); the
  `IndexOutOfBoundsException` class (deck `dc-863943`, seed-pinned, replay
  with `-Danvil.crash.trace`; plausible upstream filing).
- **Tooling riders:** ~~`final_read.py` notify hook + stdout line-buffering +
  `pool_version` provenance~~ — **correction (same day): already shipped
  2026-07-26 (`e012736`, same unabsorbed session as the collate fix)**. The
  pool-manifest mtime-selection hazard remains open, with raised stakes:
  `final_read` provenance now derives through the mtime-sorted
  `latest_pool_manifest()`, so a stale pick stamps wrong provenance.
- **Serving-path profiling (surfaced by the same session, `f9f344f`):**
  post-collate, generation is ~80% of run cost and w=8 already saturates
  the server's ~189 rps ceiling (~5.3 ms/request for a 42M model —
  per-request Python overhead suspected, not GPU). The follow-on throughput
  lever for M4-era runs; fresh-context task, noise floor first.
- The falsified-lever ledger and lr brackets are M3 assets M4 plans
  against, not around: temperature, batch size, and feature-alone are
  closed questions on this recipe.
