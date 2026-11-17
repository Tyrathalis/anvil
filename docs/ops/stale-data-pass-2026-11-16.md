# The M12 stale-data pass — kill list for sign-off (2026-11-16)

**Nothing has been deleted.** This is the inventory and the proposed list ([ADR-0126](../decisions/ADR-0126-m12-closeout.md) decision 5). The per-group inventory behind it, 1,915 groups with size, mtime and reference counts, is [stale-data-inventory-2026-11-16.tsv](stale-data-inventory-2026-11-16.tsv). Sizes are `du` in GiB. Reference counts come from name matching, not from opening each referencing file.

## Where the space is

`data/` holds about 1,219 GiB and the volume has 1.7 T free, so nothing here is urgent.

| Class | GiB | What it is |
|---|---|---|
| Keep | about 615 | 560 of it is the big run, held whole; the rest is checkpoints of record, baseline-era arm stores, banks, Ante certs, drills and evalsets |
| Ask | about 592 | the big run's ingested store, the shakedown and settings-pass stores, older milestones' loops |
| Kill candidates | about 12 | smokes, bench and profiling scratch, rebuildable jars |

**The largest lever is not on the kill list.** Raw `workers/` output under `data/runs` is 570 GiB of that directory's 710. Earlier passes deleted `workers/` wherever an ingested store in `data/trajectories` carried the games (ADR-0062, ADR-0096, ADR-0100). No ingested store's completeness has been verified in this pass.

## Decision 1 — the kill candidates (about 12 GiB)

Proposed for deletion on sign-off:

| What | GiB | Note |
|---|---|---|
| Smoke dirs under `data/runs` (153 entries, including `h2h-smoke-aa*`, `loopwire-smoke*`, `build0-smoke*`) | 1.9 | `drill-sweep-smoke` is excluded: it holds a `drills.jsonl` |
| Smoke checkpoints under `data/training` (12 entries) | 2.9 | ADR-0113 names `loopwire-smoke3` once, as a narrative |
| Smoke stores under `data/trajectories` (60 entries) | 0.3 | |
| Bench and profiling scratch (`genbench-*`, `jfr-20260914*`, `deep-bench-*`, `fleet-bench*`, `labelbench-*`; 71 entries) | 3.9 | **Hold these until the wall-cost measurement is designed**, in case a bench baseline is wanted |
| Snapshot jars not named as keeps (about 51 files under `data/runs/build{2,3,4}-*`) | about 3.0 | Rebuildable from the fork commits in the fork lineage. `forge-b3pcal.jar` is excluded: the gate's step 0 re-reads that run |
| Profiling dumps and smoke logs elsewhere | under 0.1 | |

## Decision 2 — the big run (about 665 GiB with its ingested store)

Held whole for now. Three thinning options, none proposed until the M13 arms' start is designed:

- **Per-iteration weights.** `data/training/big-run` holds 514 iterations at about 334 MiB each. Keeping the iterations cited by path (099, 301, 405, 513 and the event reads 238, 259, 289, 291), the loop state and the analysis frees about 165 GiB. A ladder of every 25th iteration frees about 161.
- **Raw `workers/` of the generation stores.** 275 GiB sits beside same-named ingested stores. Deleting it keeps `run.json`, `pairs.txt`, `games.jsonl`, `summary.json` and `mu.jsonl` (the ADR-0052 rule) and needs a completeness check of each ingested store first.
- **The in-loop arm reads** (`big-run-arm-*`, `big-run-armla-*`, 48 GiB) have no ingested store. They are the run's per-iteration strength series.

## Decision 3 — the shakedown and settings pass (about 217 GiB)

Eleven loops across `data/runs` (114), `data/training` (55) and `data/trajectories` (33), plus their arm reads (14). ADR-0115 keeps the arms' final checkpoints as the era ladder. Proposed, for the user's yes or no:

- keep each loop's final checkpoint, the iterations cited by path (`shakedown-alloc/iter-019`, `settings-stopgrad-t3e6/iter-019`, `settings-recovery/iter-006`, `settings-anchor-w01/iter-017`) and the ingested stores;
- delete the other per-iteration weights (about 50 GiB) and the raw `workers/` that an ingested store covers (about 97 GiB, after the completeness check).

## Decision 4 — M6 to M11 (about 190 GiB)

- **`d6-run*`**, 15 loops across training (72), runs (39) and trajectories (20). `d6-run11/iter-019` is the era reference and is kept. Thinning the weights to the iterations cited by path frees about 68 GiB. These stores survived five earlier passes, so they are a question, not a proposal.
- **M10 and M11 stores** (about 55 GiB): the `sched-*` paired reads, `choice-probes-m11`, the `m10-probe*` and `m10-planner-distill*` checkpoints. ADR-0096 kept the paired-read dirs as reads of record and kept `m10-planner-distill-hand2/last.pt` by name.
- **`critic-lookahead-cl2` and its forks** (1.9 GiB). ADR-0100 kept them "through M12 Build 1". That condition has lapsed. The Build 1 bank in `data/runs/m12-build1` is three files and looks self-contained; not verified.

## Decision 5 — M12 build-era stores (about 60 GiB)

The Build 2 to 4 arm and label stores. `b3-surflab*` and `b4-tgtlab` (about 13 GiB) are the label corpora behind the served surface build and are almost all raw `workers/`. Proposed: keep them until M13 decides whether any head is refit.

## Found in passing

- **Two paths in ADR-0124 do not exist:** `data/runs/seg3-bank/` and `data/training/big-run/iter-301-refit/`. What was built is `iter-301-rechead` and `data/runs/run-holdout-seg4`.
- **The fork lineage names no snapshot jar path.** CLAUDE.md's state table now names the three serving jars itself.
- **An earlier pass over-deleted once** (ADR-0063; restored from the kopia snapshot). Any `workers/` deletion in this pass is preceded by a kopia snapshot check.
- **State outside `data/`:** 41 run state files and 326 alert rows (95 unacked) under `~/.local/state/anvil`; `anvil.runs prune` is not scheduled.
