# Infrastructure survey, 2026-11-09 — run supervision, monitoring and automation

**Doc status:** survey · read-only audit of the run launcher, watchers, GPU / memory coordination, alert paths, user units and loop guards, taken 2026-11-09 17:30–17:50 PST beside the live big run (segment 5); findings and proposed fixes, nothing here is applied

## Verdict

The big run is healthy, and the layer that is supposed to tell someone when it stops being healthy has three holes at once.
**The run has no working stall detector.** The memory sampler writes `memory.jsonl` into the launcher's watched run dir every 20 s, so the supervisor's stall tick sees a fresh artifact forever; the standing watcher was the only one that could see the loop go quiet, and its registration was dropped today.
**The run's check-in is off and stays off.** One expired login on 10-16 recorded `checkin: none` in the state file, and every relaunch since has reused it; five failures and three segment closes since then reached the alert queue and the desk only.
**No path reaches the phone by itself.** By the check-in's own records, 45 of its 46 successful runs report the push as suppressed, and `ANVIL_NOTIFY_CMD` is unset in every process and unit.
What covers the run tonight is the babysitting session's background `anvil.runs wait` and its glances, and both live in the desktop app's cgroup beside the supervisor.

Behind those three sits one structural issue: the supervisor and the run do not share a fate. The run has its own scope; the supervisor stays in whatever cgroup launched it. An OOM kill of the app leaves a live, unsupervised run that the sweep then tries to launch a second time, and nothing stops two loops on one directory.

The GPU and memory coordination itself is sound: one detector with one hysteresis for the harness yield and the training gate, and three memory rules that act at three different moments. The gaps there are in what is promised (the `avoid` mark does not cover swap kills) and in waits that have no upper bound.

Everything below was checked against the code in this worktree (branch `claude/infra-survey-e17ba4`, main at `b590e99`) and the live box. Two claims are by reading only and say so.

## Ranked findings

"Live" = safe to do while the big run is running. "Boundary" = wait for the segment-5 wall stop: `anvil/runs.py` is imported by every new harness process, and `scripts/big_run_chain.sh` is read incrementally by the live bash, so neither is edited on main mid-run.

### Real issues

| # | Finding | Risk to an unattended run | Proposed fix (size) | When |
|---|---|---|---|---|
| 1 | The supervisor's stall tick is blind on the big run: `memory.jsonl` is always fresh in the watched dir | A hung loop (a deadlocked loader, a wedged harness) is never reported; today's retirement of the standing watcher removed the last detector | Skip the sampler's and the launcher's own files in `newest_mtime` (≈ 8 lines + a test); merge it with `retire-watchd-under-launcher` | Boundary. Live stopgap: the babysitter's glance reads the age of `seg-5.loop.log` and `monitor.jsonl` |
| 2 | `checkin: none` is sticky across relaunches since 10-16 | `failed`, `gone` and `done` raise no check-in: no relay to the launching session, no push | Record the requested mode, re-resolve and self-test on every relaunch, add `relaunch --checkin` (≈ 10 lines + a test) | Boundary. No code needed for segment 6: after the run exits, set `"checkin": "auto"` in the state file, then relaunch |
| 3 | The phone push is never delivered and `ANVIL_NOTIFY_CMD` is unset | Nothing reaches a human away from the desk unless a live session relays it | Wire `ANVIL_NOTIFY_CMD` to ntfy (the quickstart's two-line script); let `alert()` fall back to a fixed file path so units and relaunches need no env plumbing (≈ 6 lines) | Script: live. Code: boundary |
| 4 | Supervisor and run do not share a cgroup or a fate | App OOM-killed: the run is orphaned and the sweep launches a second chain on the same loop dir. Reboot or sweep resume: the relaunch dies with the sweep service | Supervisor joins the run's scope (≈ 20 lines); the sweep refuses to relaunch while the recorded child pid is alive (≈ 8); an exclusive lock on the loop dir in `selfplay.py` (≈ 8) | Boundary, with a scratch-state proof first |
| 5 | `ManagedOOMPreference=avoid` does not cover swap kills | The kill class that hit the run twice ignores the mark; generation has no memory guard at all | Correct the docs now; decide between extending the watchdog to generation (it writes the harness's `YIELD` file) and a root-side oomd setting | Docs: live. Code: boundary |
| 6 | Deliberate waits are unbounded and silent | A GPU or memory wait of any length heartbeats the stall alarm quiet and tells nobody | The heartbeat carries `since`; the supervisor raises one `waiting` alert past a threshold (≈ 15 lines). Align ComfyUI's unload threshold with the yield rule's 1,024 MB | Boundary. The ComfyUI env line: live |
| 7 | `anvil.runs wait` never returns on `paused` or swept `gone` | The launching session's belt hangs forever on exactly the states it exists for | Return on every terminal state (3 lines + a test) | Boundary |
| 8 | A pause line records `done` | The loop's own memorization pause, a hand-written STOP and a closed segment all read `DONE rc=0` | The chain marks a self-pause; the supervisor records `paused` with the reason and does check in (≈ 10 lines) | Boundary |
| 9 | `resume_count` is a lifetime counter | 1 of 3 resumes was spent on 10-10; two more dead supervisors in the remaining weeks and the sweep stops resuming | Reset on a manual relaunch (1 line) | Boundary. Or set it to 0 in the state file after the run exits |
| 10 | The memory watchdog picks its kill set by command-line substring, and its trip marker follows the sampler's owner | A process whose command line contains `anvil.training.rl` counts as a learner; a sampler armed by another run puts `WATCHDOG-TRIP` where the chain's retry never looks | Kill by the run scope's `cgroup.procs`; write the trip marker to the state dir (≈ 15 lines) | Boundary |
| 11 | Baseline-relative guards are single-row against a single-row iteration-0 baseline, and the only response is a halt | Each sample event stops a multi-week run until a human arrives; two so far (239, 416) | Ride the routed casts change: one multi-row form for casts, alloc / distill share, entropy and veto | Boundary (already routed for casts) |
| 12 | The wall excludes some waits and not others | Segment length in productive hours is off by ≈ 1%; `yielded_s` under-reports | Count arms yields and the learner's park; persist the state before an exit (≈ 12 lines) | Boundary |
| 13 | One SIGTERM to the supervisor becomes ≈ 1,000 to the whole run | `pause --now` and a service stop hard-kill every worker; "the harness drains" is not what happens | `start_new_session=True` on the child, forward to its group only (2 lines) | Boundary |

### Redundancies

| # | Finding | Proposed fix | When |
|---|---|---|---|
| R1 | The standing watcher is still enabled, ticks every 10 min with no registration, and its remaining callers are blind or dead | Retire it fully in the same change as finding 1: `watch_register` a no-op everywhere, the timer disabled, the repo unit copies removed | Boundary |
| R2 | The memory sampler is armed twice, by the launcher and by the chain | Drop the chain's `arm_memsampler`; the launcher's is the one that records the owner | Boundary |
| R3 | A guard halt, a crash and a segment close each notify twice or more, and the reason is in the note the check-in does not read | Under a launched run, `notify()` writes a queue annotation under the run's name and skips the sinks; the chain's FAILED line carries the loop log's last guard line | Boundary |
| R4 | Two remote-control units run side by side | Keep `anvil-rc-server`; retire the 09-21 trial unit, or keep it on purpose as the relay's fallback inbox and say so | Live (the user's call) |

### Cosmetic leftovers

Listed in their own section below; the deletion pass belongs to the milestone closeout.

## Evidence

### 1. The stall tick cannot fire on the big run

The supervisor's tick takes the newest mtime under the run dir and every `--watch` root ([anvil/runs.py:458-463](../../anvil/runs.py), [:541-547](../../anvil/runs.py)). The launcher arms the memory sampler with its output inside that same dir ([anvil/runs.py:436](../../anvil/runs.py): `out = run_dir / "memory.jsonl"`). The sampler appends one row every 20 s for as long as the unit lives.

```
$ cat ~/.local/state/anvil/memsampler.json
 "run": "big-run", "out": ".../data/runs/big-run/memory.jsonl", "armed": "2026-11-07T20:54:35-08:00"
$ ls -la --time-style=full-iso data/runs/big-run/    (17:30:05)
 42106106 2026-11-09 17:29:51 memory.jsonl
     74 2026-11-09 17:15:35 heartbeat.json
```

The run's stall threshold is 10,800 s (`stall_sec` in the state file). The sampler has written to this dir since 10-17: by hand first, from the chain since 10-21, from the launcher since 10-29. The queue holds no `stalled` alert for `big-run` in the run's five weeks.

The supervisor's quiet during today's 91-minute GPU wait was credited to the heartbeat. It would have been quiet without it. The standing watcher watched `data/training/big-run`, which holds no sampler file, so it was the one detector that could see the loop dir go silent; its registration was dropped at 17:26 and `~/.local/state/anvil/watch/` is empty. The branch `retire-watchd-under-launcher` states in its docstring that the supervisor "is that run's one stall watcher"; on the big run that watcher is blind until this is fixed.

Fix: `newest_mtime` skips a small set of names the launcher itself produces (`memory.jsonl`, `supervisor.log`); `heartbeat.json` stays counted on purpose. Alternatively the sampler writes under the state dir and only `WATCHDOG-TRIP` stays in the run dir. The quickstart's own example launches with `--dir` set to the loop dir and promises a 60-minute alarm, so external users have the same blind tick.

### 2. The check-in is off for the big run, permanently

```
$ grep checkin ~/.local/state/anvil/runs/big-run.json
 "checkin": "none",
$ anvil.runs alerts (big-run rows)
2026-10-16T20:31:15 big-run checkin  for done 059c3ccb5808: claude -p rc=1 (0 s): Failed to authenticate: OAuth session expired and could not be refreshed
2026-10-16T20:34:59 big-run checkin_unavailable  claude -p self-test failed ... no LLM check-in will run for this launch
2026-10-17T17:44:15 big-run failed  rc=-9 ...        (no check-in record)
2026-10-17T17:52:32 big-run failed  rc=1 ...         (no check-in record)
2026-10-24T14:27:34 big-run failed  rc=1 ...         (no check-in record)
2026-11-03T17:19:37 big-run failed  rc=1 ...         (no check-in record)
2026-11-08T18:43:33 big-run failed  rc=1 ...         (no check-in record)
```

The supervisor stores the resolved mode, not the requested one ([anvil/runs.py:491-496](../../anvil/runs.py)). `relaunch` passes the stored value back in ([:813](../../anvil/runs.py)). `checkin_mode("none")` returns `none` without a self-test, so a downgrade made for one launch outlives the login that caused it. Confirmed in this worktree: `_relaunch_args({'checkin': 'none', ...}).checkin` is `none` and `checkin_mode` returns `none`. Every other run launched since 10-26 self-tested and checked in normally; `big-run` is the only state file with `checkin: none`.

The launching session, `Segment 5 launch [ad8d2e]`, is live and idle in ListAgents, so the relay would reach it if the check-in ran.

A hand edit while the run is live does not hold: the supervisor rewrites the file from its in-memory copy at exit. Edit after the wall stop, before `relaunch`.

### 3. Nothing reaches the phone

```
48 checkin records; 46 ok; 45 report the push suppressed; 1 does not mention it
suppressed between 00:00 and 06:00: 09-30 05:00, 10-04 02:48, 10-04 04:29, 10-04 05:12, 10-04 05:12
```

The typical record reads "The push was not sent because the terminal is active". It reads the same at 02:48 and at 14:00, so "active" is not the user at the keyboard. The cause is not established here; the two idle remote-control sessions held open in tmux are one candidate, the headless session's own terminal another. A five-minute test settles it.

`ANVIL_NOTIFY_CMD` is unset in the live supervisor's environment (`/proc/1063409/environ` holds no `ANVIL_*` variable), in `anvil-runs-sweep.service` and in `anvil-watch.service`. Wiring it was routed in ADR-0107 on 09-15 and named again as "the belt" in the 09-21 addendum.

So the chain for any event is: queue, desk toast, and — when the check-in runs — a SendMessage relay that wakes a session, which may then push. For the big run the check-in does not run (finding 2). What remains is the babysitter's `anvil.runs wait --name big-run --poll 300` (pid 1063574), which dies with the app and hangs on two states (finding 7).

Fix: the ntfy script from the quickstart, and a fallback in `alert()` and `notify()` to an executable at a fixed path (for example `~/.config/anvil/notify`) when the variable is unset. A file needs no environment, so the supervisor, the sweep unit and a relaunch from any shell all find it.

### 4. The supervisor and the run do not share a fate

```
$ cat /proc/1063409/cgroup     (the supervisor, `anvil.runs relaunch`)
0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-com.anthropic.Claude-2666057.scope
$ cat /proc/1063410/cgroup     (the chain)
0::/user.slice/user-1000.slice/user@1000.service/app.slice/anvil-big-run-1063409.scope
```

`_child_cmd` wraps only the child in the scope ([anvil/runs.py:367-397](../../anvil/runs.py)). Two consequences.

**(a) The app is killed, the run survives, the sweep duplicates it.** oomd kills a cgroup with SIGKILL, so the supervisor dies without running its handler and the chain carries on in its own scope. Within ten minutes the sweep finds `running` with a dead supervisor, marks it `gone`, and — the run is `resume: true`, count 1 of 3 — calls `launch()` ([:856-872](../../anvil/runs.py)). `launch()`, `relaunch()` and `sweep()` check only the supervisor's pid ([:583](../../anvil/runs.py), [:828](../../anvil/runs.py), [:856](../../anvil/runs.py)); none looks at the recorded child pid. Nothing in `selfplay.py`, the harness or the chain holds a lock on the loop dir (no `flock`, no pidfile). A second loop that reaches a mid-generation iteration deletes the first loop's live behaviour-policy log: `mu_path.unlink()` at [anvil/training/selfplay.py:2249-2250](../../anvil/training/selfplay.py) runs when no batch of the iteration has been ingested yet, which is the whole of generation. How far the second loop gets depends on consequence (b).

**(b) The sweep's relaunch is killed when the sweep service ends (by reading, not reproduced).** The relaunched supervisor is a double-forked child of `anvil-runs-sweep.service`, a `Type=oneshot` unit with the default `KillMode`. When `ExecStart` exits systemd terminates what is left in the unit's cgroup. The supervisor's SIGTERM handler forwards the signal to the child's process group ([:520-524](../../anvil/runs.py)), and the child was spawned without a new session, so that group is the whole run. This is the 10-10 failure ("died with the sweep service's cgroup 9 s later") with one process moved: the fix put the chain in a scope, the supervisor that signals it is still in the service. The queue holds one `relaunched` alert, from 10-10; the path has not run since the fix. Every reboot since was a planned `pause`, which the sweep ignores.

Why this is the expected path and not an exotic one: the box has been OOM-killed twice with this run on it, and the design intent of the scope is that the desktop dies first.

The proof is two minutes at the boundary: a scratch `ANVIL_STATE_DIR`, a `sleep 600` run with `--resume-on-gone`, kill its supervisor, run the sweep from a transient oneshot unit, and watch whether the relaunch outlives the unit. It needs a unit start, which this survey was not allowed.

Fix, one mechanism: `launch()` re-executes itself under `systemd-run --user --scope` before forking, so supervisor and child live and die together and both outlive the app and the sweep. Then the two guards that make every duplicate-launch path safe whatever caused it: the sweep and `launch()` refuse while the recorded child pid is alive (state `orphaned`, one alert), and the loop takes an exclusive `flock` on `<out>/loop.lock` at startup.

### 5. The `avoid` mark does not cover swap kills

From this box's `systemd.resource-control(5)` (systemd 262):

> When calculating candidates to relieve swap usage, systemd-oomd will only respect these extended attributes if the unit's cgroup is owned by root.

```
$ stat -c '%U:%G' /sys/fs/cgroup/.../app.slice/anvil-big-run-1063409.scope
tyrathalis:tyrathalis
$ getfattr -d -m user.oomd .../anvil-big-run-1063409.scope
user.oomd_avoid="1"
$ oomctl
Swap Used Limit: 90.00%
```

The mark is set and the scope is user-owned, so it counts for memory-pressure kills under the user manager and not for swap kills. Both recorded kills came with swap near its limit (60 GB used on 10-10). The second one, 10-17, hit "the run's own scope at 58 GB resident + 47 GB swapped" ([scripts/memory_sampler.sh:2-3](../../scripts/memory_sampler.sh)) seven days after the mark landed. The quickstart says "`systemd-oomd` kills other things first" and the launcher's docstring says the mark "tells oomd to kill the desktop first"; both hold for pressure only.

The working defence on the swap path is the memory watchdog, and it acts only while a learner is up ([scripts/memory_sampler.sh:61-63](../../scripts/memory_sampler.sh)). During generation — 24 JVMs at 2 GB plus the servers, beside ComfyUI's offload and the user's games — nothing acts before oomd. Over the last 24 h `MemAvailable` bottomed at 11.0 GB with no learner up and 15.2 GB with one; swap stands at 16 of 62.5 GB. There is margin today.

Options: correct the two sentences and record the watchdog as the swap-path defence; or let the sampler write the harness's existing `YIELD` file when memory is low in generation, so no new chunk launches and the JVMs drain (one gate reused, not a new one); or raise oomd's swap limit as root. The first is owed regardless.

### 6. Waits with no upper bound

Each deliberate wait loops until its condition clears and heartbeats once a minute: the training-step GPU gate ([anvil/training/selfplay.py:511-522](../../anvil/training/selfplay.py)), the host-memory wait ([:561-574](../../anvil/training/selfplay.py)), the learner's VRAM park ([anvil/training/vram.py:81-95](../../anvil/training/vram.py)) and the harness yield ([anvil/bridge/harness/orchestrator.py:382-384](../../anvil/bridge/harness/orchestrator.py)). The heartbeat exists to keep the stall alarm quiet, and it does so with no limit. A ComfyUI job left running for a day, or a tenant that holds memory under the 40 GB floor, parks the run silently. `vram.py`'s docstring still says "the watchd stall alert (75m) doubles as the page if a park outlives it"; under the launcher the opposite is true.

One threshold mismatch feeds this. The yield rule treats a process holding ≥ 1,024 MB as foreign ([anvil/bridge/harness/gpu_yield.py:11-14](../../anvil/bridge/harness/gpu_yield.py)); the idle-unload timer acts only at ≥ 2,048 MB (`COMFY_VRAM_MB`). An idle ComfyUI holding between the two is foreign forever and never unloaded.

Fix: `heartbeat()` records when the current note began; the supervisor raises one `waiting` alert, with the note, when a wait passes a threshold, and one `recovered` when it ends. The alarm then says "waiting on ComfyUI for 3 h" instead of nothing or a false STALLED. Set `COMFY_VRAM_MB=1024`.

### 7. `anvil.runs wait` hangs on `paused` and `gone`

`wait` returns for `done` and `failed`, and for `running` with a dead supervisor ([anvil/runs.py:692-702](../../anvil/runs.py)). A state file that already says `gone` (the sweep got there first, which at a 300 s poll against a 600 s timer is the usual order) or `paused` matches neither branch.

```
$ ANVIL_STATE_DIR=<scratch> python -m anvil.runs wait --name x-gone --timeout 3 --poll 1
x-gone: wait timeout        (rc 3; without --timeout it never returns)
$ ... wait --name x-paused --timeout 3 --poll 1
x-paused: wait timeout      (rc 3)
```

### 8. A pause line reads as `done`

The loop writes STOP at an ADR-0124 pause line and exits cleanly ([anvil/training/selfplay.py:2963-2974](../../anvil/training/selfplay.py)). The chain sees STOP and exits 0 ([scripts/big_run_chain.sh:203](../../scripts/big_run_chain.sh)). No `pause_requested` is on the state, so the supervisor records `done` ([anvil/runs.py:556-572](../../anvil/runs.py)). The same happens for a STOP written by hand. `status` then shows `done` for a run that is paused mid-segment and wants a human read. The quickstart documents it ("the launcher records `done`"). The pause line has not fired on the big run, so this path is unexercised.

### 9. `resume_count` never resets

```
$ grep resume ~/.local/state/anvil/runs/big-run.json
 "resume": true, "resume_max": 3, "resume_count": 1
```

The count was spent on 10-10 and has ridden through every manual relaunch since ([anvil/runs.py:815](../../anvil/runs.py)). The cap is meant to stop a crash loop; as written it is a budget for the run's whole life.

### 10. The memory watchdog's identity and bookkeeping

- The learner is found by substring: `'anvil.training.rl' in cmd or '/rl.py' in cmd` ([scripts/memory_sampler.sh:47](../../scripts/memory_sampler.sh)). Any process with that text in its command line counts, including a session shell running a `grep` for it, and the kill set descends from every match by ppid ([:68-76](../../scripts/memory_sampler.sh)). This is the pattern-derived identity the 07-31 post-mortem retired for the watcher. A false kill needs two low samples 20 s apart with such a process alive, so it is unlikely, but the fix is cheap: the run's scope lists its own pids in `cgroup.procs`.
- `WATCHDOG-TRIP` is written beside the sampler's output ([:87](../../scripts/memory_sampler.sh)), and the output dir belongs to whichever run armed the unit. The chain's halving retry reads `$OUT/WATCHDOG-TRIP` only ([scripts/big_run_chain.sh:198](../../scripts/big_run_chain.sh)). Today the owner is `big-run`, so the two agree. After a reboot, a read launched before the big run would own the sampler, the launcher would leave it alone ("armed by a run that is still live"), and a trip would land where the chain never looks.
- A trip raises no alert. The dying loop sends a "DRIVER CRASHED CalledProcessError(-15 …)" toast, and the chain logs the retry to `queue.log`.
- The unit is transient with no `Restart=`. If it dies mid-segment nothing notices until the next launch.
- No trip has occurred in segment 5: `data/runs/big-run/WATCHDOG-TRIP` does not exist.

### 11. Guards

The casts guard's basis (decision windows per game × cast share) is routed and not repeated here. The same shape holds for its neighbours, and the routed change should cover them in one form:

- `alloc_share` and `distill_share` are a term's weighted loss over the batch's policy-gradient magnitude ([anvil/training/selfplay.py:1157-1160](../../anvil/training/selfplay.py)). Iteration 239 halted on the denominator. The response was a threshold raise to 0.10; the chain's own comment records that the denominator has drifted 18% over the run.
- `ent`, `veto_rate` and `casts_per_game` compare one iteration's row against one iteration's baseline, iteration 0, 428 iterations ago ([:1233-1242](../../anvil/training/selfplay.py)).
- Every breach is a halt (`--guard-action halt`). The rollback action exists and is unregistered.

No two guards cover the same failure. The kl guard on the iteration mean and the in-phase `--kl-abort` at five times it are the same quantity at two time scales. Veto and casts bound the rejected-intent penalty from both sides. The Spearman floor (0.30) sits five standard errors under the last row (0.45) on a frozen bank, with no sample term in its basis.

Separately, the run's kl, entropy and arms "watch lines" are session practice, not code: they exist while a babysitting session remembers to compute them. The ADR-0124 pause line is the mechanism that already does this in the loop; the multi-row change is the place to move them.

### 12. Wall accounting

```
loop_state: wall_used_s 704.1 h, yielded_s 64.05 h
ledgers:    generation yields 63.86 h (88 ledgers), training-step GPU wait 1.63 h   -> 65.49 h
            arms yields 3.91 h (17 ledgers under data/runs/big-run-arm*)            -> not excluded
```

- Generation yields and both training-step waits come out of the wall ([anvil/training/selfplay.py:2347-2355](../../anvil/training/selfplay.py), [:2434-2444](../../anvil/training/selfplay.py)). The arms phase launches four harness runs every fifth iteration and reads no ledger ([:2976-3040](../../anvil/training/selfplay.py)), so 3.9 h of yielding counted as productive time.
- The learner's VRAM park happens inside `rl.py` and leaves no ledger; it counts as productive time.
- An iteration interrupted by a crash, a kill or a guard halt adds nothing to the wall: `wall_used_s` is written only on an accepted iteration, a rollback or a STOP exit ([:2209](../../anvil/training/selfplay.py), [:2845](../../anvil/training/selfplay.py), [:2879](../../anvil/training/selfplay.py)), and the halt exits with "loop_state unchanged" ([:2852-2862](../../anvil/training/selfplay.py)). At least five such events so far.
- The same exits drop that iteration's yield from `yielded_s` while its `yield.json` marker says counted, which is the likely source of the 1.44 h gap between the state and the ledgers (by reading; not traced event by event).

The net error is about 1% of a segment. It matters for equal-box-time arms more than for this run.

### 13. The signal forward

The child shares the supervisor's process group (live: supervisor, chain, `uv`, the loop, the harness, both servers and all 24 JVMs are in pgid 1063408). The handler signals that group, which includes itself, so it re-enters until the interpreter's recursion limit. A standalone mimic with the handler's exact shape:

```
child saw 623 SIGTERMs in 4 s
supervisor handler ran 999 times
```

`pause --now` signals the same group directly ([anvil/runs.py:789-796](../../anvil/runs.py)). Its help text says "the harness drains its games"; every worker JVM receives the SIGTERM itself. Games resume at seeded granularity, so nothing is lost but the in-flight games.

### R1. The standing watcher after the retirement branch

- `anvil-watch.timer` is enabled and ticks every ten minutes; since 17:26 it has no registration to check.
- `scripts/final_read.py:145` registers every read against `data/runs` as a whole, with a 45-minute stall. That tree has 4,696 entries and takes a sampler row every 20 s, so the registration cannot stall. Under the chain it also adds a GONE toast beside the supervisor's `failed` on a crash.
- `scripts/fleet_bench.py:104` does the same at 90 minutes.
- Twelve older scripts call `anvil_watchd.py` or `watch_register` directly; none has been touched since 09-27.
- `check()` and `unregister()` read-modify-write `watch-state.json` without a lock. A stale entry is the result: `{"br-simhybrid-read": "RUNNING"}` for a read that ran 10-03 11:18–11:22. It has no process, no registration and no `anvil.runs` state. The brief for this survey named it as a live run.
- ADR-0107 says both "kept as a Linux belt" (decision 5) and "stays retired in place" (09-18 addendum).

After the branch merges, the watcher's only remaining subjects are processes started outside the launcher, which the standing rule already forbids for long runs. One stall watcher per run means this one goes.

### R2. Two arms for one sampler

The launcher arms the unit on every detached launch and records the owner ([anvil/runs.py:403-444](../../anvil/runs.py)). The chain arms it again before every loop start and records nothing ([scripts/big_run_chain.sh:134-142](../../scripts/big_run_chain.sh)). The chain's copy predates the launcher's by eight days. Each chain start logs "memory watchdog anvil-memsampler: active". The one case the chain's copy covers and the launcher's does not is a sampler that died between two retries inside one chain process; a `Restart=on-failure` on the unit covers that and the mid-segment case too.

### R3. Double notifications

`notify()` appends a `note` to the queue and fires the sinks ([anvil/training/notify.py:59-95](../../anvil/training/notify.py)); the supervisor then alerts on the exit. A guard halt is two toasts, a crash two, a segment close four (COMPLETE, two "read complete", DONE). ADR-0107 decision 6 said chains stop notifying themselves; the loop and the read script still do.

The useful half is in the wrong place. The guard's name is in the note. The supervisor's `failed` alert carries the tail of `run.log`, which for the chain is "segment 5 loop FAILED rc=3 (a guard halt or a crash; read …)". The notes are filed under the tag (`selfplay`, `final_read`), not the run's name, and nothing ever acks them.

### R4. Two remote-control units

`anvil-rc-server.service` and the 09-21 trial `anvil-remote-control.service` are both enabled and both alive since the 11-06 boot (tmux `anvil-rc-server` and `anvil-rc`). The server spawns sessions in worktrees. The trial holds one idle session, `anvil-box`, in the main checkout. That session is the check-in relay's fallback target: 27 of the 46 check-in records name it as the recipient or report a fallback (the earliest under the 09-18 broadcast rule). It is also the kind of session that wrote the duplicate closes of 10-01 and 10-03. It may also be what keeps "the terminal active" for finding 3.

## Who can see which quiet phase

"Supervisor" assumes finding 1 is fixed; today it sees nothing. "Standing watcher" is the pre-retirement registration on the loop dir.

| Phase | What it writes | Supervisor | Standing watcher | Wall |
|---|---|---|---|---|
| Generation | harness lines in the loop log (run dir); `mu.jsonl` in the loop dir | sees | saw | counted; yields excluded |
| Harness GPU yield | marked progress lines; `gpu-yield.json`; heartbeat | sees | saw only `mu.jsonl` going stale | excluded |
| Training-step GPU gate | a log line every 300 s; heartbeat | sees | **blind** (today's false STALLED) | excluded |
| Host-memory wait | a log line every 300 s; heartbeat | sees | blind | excluded |
| Training step | `metrics.jsonl`; learner output in the loop log | sees | saw | counted |
| Learner VRAM park | a log line every 30 s; heartbeat; one desk toast | sees | saw only via the train dir | **counted** |
| State-ranking eval | nothing until it ends (≈ 25 s, timeout 30 min) | silent, short | silent, short | counted |
| Arms rows | harness lines; `arms-server.log` | sees | saw | counted; **yields counted** |
| Paired read (`--paired-read`) | a progress row every 300 s in the loop dir | sees | saw | yields excluded |
| Segment reads (chain) | `seg*.log` in the run dir; `br*` arm dirs | sees | loop unregistered; the read's own registration is blind | not in the wall |
| Between segments | nothing; the run is `done` | none needed | none | — |
| A queue in `anvil.runs wait` | heartbeat on its own run | sees | n/a | — |

No phase is invisible to the supervisor once `memory.jsonl` stops masking it. The `--watch 'data/runs/br*'` root matches read dirs only (125 of them), not the loop's `big-run-i*` or `big-run-arm*` dirs; that is harmless because both narrate into the run-dir log. The whole tick walks 28,838 files in 0.15 s.

## GPU and memory rules side by side

| Rule | Acts when | Threshold | Hysteresis | Tells anyone | Wall |
|---|---|---|---|---|---|
| Harness yield | before each new chunk | a foreign compute process with ≥ 1,024 MB or ≥ 20% SM | 60 s on, 120 s off | no | excluded |
| Training-step GPU gate | once, before the learner starts | the same detector | 0 s on, 120 s off | no | excluded |
| Learner seg-halving, then park | a forward-pass OOM at seg 8 | free VRAM < 9,000 MB | none; 30 s poll | desk toast, queue note | counted |
| ComfyUI idle-unload (external) | every minute | idle 600 s while holding ≥ 2,048 MB | — | journal | — |
| Host-memory wait | once, before the learner starts | `MemAvailable` < 40 GB | none; 30 s poll | no | excluded |
| Memory watchdog | every 20 s, learner up | `MemAvailable` < 2,048 MB for 2 samples | — | trip file only | iteration dropped |
| Chain's halving retry | after a trip | `RL_WORKERS` 4 → 2, once | — | `queue.log` | — |
| Run scope `avoid` | an oomd pressure kill | oomd's own | — | — | — |
| systemd-oomd | swap 90%, or pressure | ignores `avoid` for swap | — | journal | — |

The GPU rows are one rule applied at two points, plus a mid-step backstop for the case the gate cannot see (a tenant arriving after the step starts). The memory rows are admission, mid-step eviction and last resort. That is coherent. The mismatches are the two named above: 1,024 against 2,048 MB, and a scope property credited with protection it does not give on the swap path.

## Docs against reality

| Where | Says | Is |
|---|---|---|
| `CLAUDE.md` Hard conventions | the supervisor "runs its own stall tick" and "runs a `claude -p` check-in on failed / stalled / gone / long done" | true of the launcher; false of the live big run (findings 1, 2) |
| `CLAUDE.md`, quickstart, launcher docstring | "detaches at nice 19" | the loop, the harness and both servers run at nice 15, the chain's bash at −4. `os.nice(19)` is an increment from the launching shell's −4 ([anvil/runs.py:471-475](../../anvil/runs.py)); `ananicy-cpp` is active and carries a rule for `bash`. One line: `os.setpriority` to an absolute value |
| quickstart §7½ example | `--dir data/training/mydecks-loop --stall-min 60`, "stall alarm 60 min" | the sampler writes into that dir; the alarm cannot fire |
| quickstart §7½ | the check-in "pushes one notification to your phone, messages any Claude Code session … whose title mentions Anvil" | relays to the launching session since 10-03; the push is not delivered |
| quickstart §7½ | "relaunched by the sweep timer itself … your only step is the login" | unexercised since the 10-10 failure; by reading it still fails (finding 4b) |
| quickstart §7¾, launcher docstring | oomd "kills other things first" | pressure kills only (finding 5) |
| quickstart §7¾ | two bullets describe the memory watchdog | one describes the launcher arming it, one the hand-run unit it replaced |
| quickstart coverage-line sample | ends at "check-in claude (self-test OK, 3 s)" | the line also carries the relay target and the watchdog phrase |
| ADR-0107 | the watcher is "kept as a Linux belt" and "stays retired in place" | enabled and ticking |
| `anvil/runs.py` docstring | "No registry, no timer, no per-run waiter" | a sweep timer, a sampler unit and a session-side wait per run |
| `anvil/training/vram.py` docstring | the watchd stall alert pages a long park | the park heartbeats the alarm quiet |
| `anvil.runs pause --now` help | "the harness drains its games" | every JVM gets the SIGTERM (finding 13) |
| ADR-0107, routed 10-03 | `anvil.runs stop`; a hook warning on a launch without `--launched-by` | both still open (no `stop` verb in `anvil/runs.py`; the only PreToolUse hook is the pgrep guard) |

## Cosmetic leftovers and stale state

For the closeout's deletion pass; none of these puts a run at risk.

- `~/.local/state/anvil/runs/`: 40 state files, 35 `done`, 4 `failed`, the oldest from 09-21. `prune` is never scheduled and skips `paused` and `gone`.
- `~/.local/state/anvil/alerts.jsonl`: 313 rows, 83 unacked (42 notes, 16 check-in records, 8 `done`, 7 `paused`, 6 `failed`, 4 others). Nothing drains it: the check-in acks only its own alert, and the scheduled task that drained the rest is disabled. `alerts --unacked` is therefore not a to-do list. Informational kinds could be born acked.
- `~/.local/state/anvil/watch-state.json`: the stale `br-simhybrid-read` entry (R1).
- `/tmp/anvil-memsampler.*.low`: four files, three from dead samplers.
- `data/runs/big-run/DONE`: written at segment 4's close and still present while segment 5 runs. Nothing reads it today.
- The scheduled task `anvil-run-checkin`: disabled, last run 09-16, left in place by ADR-0107.
- `scripts/systemd/anvil-watch.{service,timer}`: repo copies of the watcher's units; the sweep's units exist only as strings in `anvil/runs.py`.
- `scripts/`: 18 `launch_*.sh` from the D6 and M10 eras and 42 one-shot chain and queue scripts. `launch_ceiling.sh`, `launch_rate_sweep.sh`, `build2_*_read.sh`, `build3_pay_chain.sh`, `build3_surface_fit_chain.sh` and six others still register with the watcher.
- State-file fields nothing reads: `stalled_since`, `ended`, `error` in a run's state; `armed` in `memsampler.json`. They are for people; fine to keep.
- A run's environment is whatever shell relaunched it and is not recorded. The chain already works around this once (ParallelGC is a marker file "because `relaunch` re-runs the recorded command without the launch's environment").
- `pause` on the big run would write STOP into 23 non-harness `data/runs/br*` dirs (analysis dirs matched by the watch glob); `relaunch` removes them. A `pause` during the segment reads does not stop the read: its harness dir is skipped as "a loop's live generation".
- Stale comments: `PAIRED_HEARTBEAT_S` "(watchd stall is 75 min)" at `selfplay.py:252`; the watcher paragraphs at `selfplay.py:2153-2157` and `final_read.py:141-145`.
- Not the project's: `default.target.wants/claude-cowork.service` is a dangling link (unit not found).

## Checked and found sound

- **One GPU detector.** The harness yield and the training gate share `GpuYield` and its 120 s release. Today's wait is the proof: ComfyUI was in use until about 17:03, the idle-unload timer fired at 17:14:14 after 630 idle seconds (17,868 → 556 MB), and the gate cleared at 17:15.
- **The heartbeat reaches the supervisor.** `heartbeat.json` in the run dir carries "gpu wait: training step" at 17:15:35; the learner and the harness inherit `ANVIL_RUN_NAME`.
- **The idle-unload timer** is live, documented in `docs/ops/`, and its copy of record is in the repo.
- **The sweep timer** is enabled, last fired 17:25, and linger is on. The sweep is idempotent.
- **The sampler's owner record matches the run.** `memsampler.json` names `big-run` and the unit has been active since 11-07 20:54; the chain's retry reads the right trip file today.
- **Memory margin.** 4,320 samples over the last 24 h: `MemAvailable` minimum 11.0 GB, 15.2 GB with the learner up, no trip.
- **Another run's servers are not foreign, and need not be.** A model server holds about 1.2 GB; two runs' servers fit beside the learner on the 24 GB card.
- **The launching session is reachable.** `Segment 5 launch [ad8d2e]` is listed; the relay's ref match would find it.
- **`pause` and the loop.** `_stop_roots` keys on `run.json`, the file the harness writes; the loop root is watched; a self-written STOP is cleared on relaunch.
- **A guard-halt relaunch is deterministic.** The training `DONE` marker is reused and the same guards re-evaluate under the new threshold (416 reproduced to the third decimal).
- **The stall tick's cost** is negligible at this run's size (0.15 s per tick).
- **Routed elsewhere and not re-reported:** the casts guard's share-based or multi-row form; the learner DataLoader's decode-to-tensors change.

## Suggested order

1. **Now, no code.** The babysitter's glance checks the age of `data/runs/big-run/seg-5.loop.log` and `data/training/big-run/monitor.jsonl`; that is the run's stall detector until the boundary. Write the ntfy script. Set `COMFY_VRAM_MB=1024`.
2. **At the wall stop, before the relaunch.** In the state file: `"checkin": "auto"`, `"resume_count": 0`. Merge one bundle: `retire-watchd-under-launcher`, the stall tick's ignore list, the check-in re-resolve, `wait` on every terminal state, the notify fallback path, the watcher fully retired. Read the coverage line: it should say `check-in claude (self-test OK …)`.
3. **In the boundary window, with the two-minute proof.** The supervisor in the run's scope, the child-alive guard, the loop lock.
4. **With the routed guard change.** The multi-row form for every baseline-relative guard, the watch lines as pause lines, the wall's arms and park seconds.
5. **At the closeout's documentation pass.** The docs table above and the leftovers list.
