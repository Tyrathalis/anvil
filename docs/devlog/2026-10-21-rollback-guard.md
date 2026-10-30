# 2026-10-21 — the rolling-back guard + two launcher conveniences (worktree `kind-gagarin-7559fd`, branch `claude/kind-gagarin-7559fd`)

<!-- Wrap-up: the session checklist lives in CLAUDE.md (devlog · the running record (mNN-running-record.md) · Now block · commit). -->

Built while segment 3 of the big run flies on main (never edited). **Not merged** — the merge and the real smoke
(the chain, `anvil-memsampler`) happen at segment 3's boundary (≈ 10-29). Four commits on the branch.

## Done

- **The rolling-back guard** (`anvil/training/selfplay.py`, `4f3bfd6`): `--guard-action rollback` (default `halt`;
  the halt path byte-identical with the flag off — no halt-block line changed, and every lr string is `str(x * 1.0)`).
  On a breach under `rollback`: `REJECTED` as before, neither ckpt nor critic advances, the loop continues from the
  last accepted ckpt with the learner's lr groups (`--lr`, `--pay-lr`, `--trunk-lr`, `--value-head-lr`) multiplied
  by `--guard-lr-mult` (0.5; the base lr floored at `--guard-lr-floor` 1e-7); the multiplier rides `loop_state.json`
  (`lr_mult`) and never rises; the event is the row's `guard_rollback` and `loop_state`'s `guard_rollbacks` +
  `guard_last_rollback`; a second breach within `--guard-rollback-window` (5) iterations halts as today (with one
  extra log line saying why). `start_index` advances (fresh seeds), the wall is charged, the rejected iteration's
  stores stay in the replay window (the accepted ckpt played them). The decision is the pure `guard_decision`
  (guards, action, iteration, last rollback, window, lr, lr_mult, mult, floor → kind, new multiplier, row entry);
  `tests/test_guard_rollback.py` covers accept / halt-by-default / rollback / the compounding cut / the window's
  edge (inside → halt, one past → rollback) / the floor (clamps, never raises, 0 = off). The design note is in the
  running record (10-21 evening); the quickstart §7 flag list carries the four flags (`7c89348`).
- **`anvil.runs relaunch --launched-by`** (`anvil/runs.py`, `e7f1791`): overrides the recorded `launched_by` before
  the relaunch (printed as `launched_by 'old' -> 'new'`); without it the recorded one stays. `_relaunch_args` takes
  the override as its third argument. Test: a relaunch with the flag re-points the record and a later bare relaunch
  keeps it.
- **The chain arms the memory watchdog** (`scripts/big_run_chain.sh`, `7fed113`): `arm_memsampler` before every
  loop start (inside the retry loop, so a halved-workers rerun re-checks): `systemctl --user is-active --quiet
  anvil-memsampler` → "active"; else `reset-failed` (a failed remnant would make `systemd-run` refuse the name) and
  the header's line from `scripts/memory_sampler.sh` (`--unit=anvil-memsampler -p MemoryMax=500M -p
  WorkingDirectory=$REPO … memory_sampler.sh $OUT/memory.jsonl 20`) → "ARMED" or "FAILED to arm (rc) — the loop
  runs unwatched". One `queue.log` line either way. `MEMSAMPLER_UNIT` is overridable for smokes only. Smoked with the
  function extracted verbatim: the live unit reads active; a fake `systemd-run` recorded the exact line; a failing one
  produced the FAILED line.
- `uv run pytest tests/`: **364 passed, 41 skipped** (41.9 s).

## The smoke (the loop, `--guard-action rollback`)

Launched through `anvil.runs launch --name rb-smoke` from the worktree (data links: `embeddings`, `runs`,
`trajectories` → main; the untracked `data/pool` entries linked one by one beside the tracked `flex.txt`/`pauper`).
8 games per iteration (4 mirror + 2 + 2 heuristic), 4 workers, port 50090, the Build 4 ckpt, `--guard-kl 1e-6
--guard-action rollback --guard-rollback-window 1 --iterations 3`, the rung-2 lr flags (`--lr 1e-5 --trunk-lr 3e-6
--value-head-lr 1e-4`). 7.5 min wall, exit 0.

- **The kl guard did not fire** — at 8 games the trainer runs ~2 optimizer steps, below its logging window, so the
  row's `rl` dict is `{}` and the kl guard has nothing to read (`guard_flags` skips a missing `kl_mu`). The **veto
  guard** fired instead at iteration 1 (an 8-game veto rate is noise: 0.0241 → 0.0456 > 1.5×). The rollback path is
  guard-agnostic, so the smoke still exercises it end to end; a kl-driven smoke needs a loop big enough to log a
  window (the boundary's real smoke).
- Monitor rows (`data/training/rb-smoke/monitor.jsonl`, the relevant keys):

  ```
  {"iteration": 0, "ckpt": ".../m12-build4-e1a-tgt/last.pt", "guard": []}
  {"iteration": 1, "ckpt": "data/training/rb-smoke/iter-000/train/last.pt",
   "guard": ["guard: veto_rate 0.0456 > 1.5x iter-0 (0.0241)"],
   "guard_rollback": {"iteration": 1, "rule": "guard: veto_rate 0.0456 > 1.5x iter-0 (0.0241)",
                      "lr_before": 1e-05, "lr_after": 5e-06, "lr_mult": 0.5}}
  {"iteration": 2, "ckpt": "data/training/rb-smoke/iter-000/train/last.pt", "guard": []}
  ```

- The log at the breach:

  ```
  [selfplay] !!! GUARD ROLLBACK iteration 1: ['guard: veto_rate 0.0456 > 1.5x iter-0 (0.0241)']
  [selfplay] ckpt NOT accepted; continuing from data/training/rb-smoke/iter-000/train/last.pt with lr x0.5 (1e-05 -> 5e-06); a second breach within 1 iterations halts
  [selfplay] ===== iteration 2: ckpt=data/training/rb-smoke/iter-000/train/last.pt ===== 2026-10-21 20:31:46 (wall used 0.08 h)
  ```

- Iteration 2's trainer command carried `--lr 5e-06 --trunk-lr 1.5e-06 --value-head-lr 5e-05` (iteration 1's:
  `--lr 1e-05 --trunk-lr 3e-06`); `iter-001/REJECTED` exists; iteration 2 was accepted (`loop_state`: iteration 3,
  ckpt `iter-002/train/last.pt`, `start_index` 24, `lr_mult` 0.5, `guard_last_rollback` 1, one `guard_rollbacks`
  entry). The window-halt branch is covered by the unit test, not by this smoke (iteration 2 did not breach).

## Broke / surprised me

- `pytest --timeout` is not installed here (the first full-suite attempt died on the flag).
- The smoke's stores and run dirs live in main's `data/trajectories/rb-smoke-*` / `data/runs/rb-smoke-*` (≈ 15 MB)
  through the links — deletable at any time. The loop dir is the worktree's `data/training/rb-smoke/`.

## Next session picks up

- **At segment 3's boundary (≈ 10-29):** merge `claude/kind-gagarin-7559fd` into main (four commits, no conflicts
  expected beyond the running record's tail); the real smoke of `arm_memsampler` on a quiet box (stop the unit, run
  the chain's first lines, see "ARMED"); a kl-driven smoke of the rollback at a size that logs a window.
- **The user's call:** whether the big run's remaining segments pass `--guard-action rollback` (the chain does not;
  the registered response is still the halt — an addendum if it changes mid-run), and whether the rolled-back run's
  lower lr should ever recover (it never rises today; a `--guard-lr-recover` after N clean iterations is the obvious
  follow-up, not built).
- Routed, not built: a rollback that restores the lr multiplier; the chain's retry on a guard halt (today a halt
  exits the chain FAILED — under rollback it only happens on a repeat breach, which is the right time to stop).
