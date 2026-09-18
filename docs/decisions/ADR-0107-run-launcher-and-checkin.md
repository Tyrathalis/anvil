# ADR-0107: One launcher for detached runs, an alert queue, and the LLM check-in

- **Date:** 2026-09-15
- **Status:** accepted
- **Design-doc anchor:** §9 (harness, deterministic replay, run hygiene); operational

## Context

The evening 5 paired read failed 18 s after launch (the harness refuses `-search` without
`-labels`) and nobody knew for an hour. Every layer did what it was built to: the wrapper sent a
desk toast and unregistered cleanly from the watcher. That is the gap: desk toasts reach nobody
away from the desk, a fast clean failure is not a stall, and the session-side waiter the launch
checklist asks for (box 3) depends on the session remembering to arm it — which it did for the
forkcheck and the smokes and not for the queued read.

The run machinery had grown as layers of wrappers — a systemd-timer watcher with a registration
protocol, per-script register / finish / notify blocks (20 sites), session waiters, a five-box
checklist in memory — without cohering: every layer ends at the same two dead ends (the desk, or a
session that may not exist). Two users now run Anvil on their own machines, so whatever replaces it
must not assume systemd, `/proc`, or the desktop app.

## Decision

1. **One launcher, `python -m anvil.runs launch --name N --dir D -- <cmd>`** (`anvil/runs.py`,
   stdlib only, Linux + macOS). The launcher's detached supervisor process IS the run's watchdog: it
   detaches (double fork + setsid, stdin from `/dev/null`, `PYTHONUNBUFFERED=1`, nice 19), spawns the
   command with the log in D, writes `runs/<N>.json` as running → done | failed (exit code, log
   tail), ticks on the newest mtime under D for stalled / recovered, and appends every transition
   to `alerts.jsonl` (id, ts, run, kind, msg, acked). It prints ONE coverage line at launch. The
   checklist's five boxes are its features; the checklist retires.
2. **Failure is a recorded state, never an absence.** No registration to forget, no unregister to
   get wrong. `anvil.runs status` shows every run; a supervisor that died shows as `gone`.
3. **Delivery is a queue plus sinks.** The queue is the coverage; `$ANVIL_NOTIFY_CMD` (ntfy, mail —
   portable) and the desk toast (notify-send / osascript) are side effects. `anvil.training.notify`
   appends to the same queue, so legacy drivers' end-of-run notes land there too.
4. **The LLM check-in**: a scheduled Claude task (the desktop app, every 30 min, prompt in
   [docs/ops/run-checkin.md](../ops/run-checkin.md)) drains unacked alerts: pushes each to the
   phone, messages the supervising session with the alert and paths when one is open, acks. It is
   read-only and never fixes anything; diagnosis stays with the session that has the context. For a
   user without the app, the queue + `ANVIL_NOTIFY_CMD` is the floor; the check-in is the upgrade.
5. **Hardening stays optional and platform-gated**: `--memory-max` wraps the child in a
   `systemd-run --user --scope` where systemd exists and is ignored with a note elsewhere. The
   systemd-timer watcher (`anvil_watchd.py`) is kept as a Linux belt for drivers that self-register;
   it is no longer the front door and no new script registers with it.
6. **Chain scripts launch through the launcher and stop notifying themselves.** A chain's `fail()`
   is `exit 1`; the supervisor records the failure with the log tail. The four live chains
   (`build3_surface_read.sh`, `build3_prio_calibration.sh`, `build3_pay_calibration.sh`,
   `build3_e5_read_queue.sh`) are ported in this commit; the rest port as they are next used.

## Consequences

- Standing rule → [standing-rules.md](../standing-rules.md) (engine / data hygiene → runs): **every
  detached run launches through `anvil.runs launch`; the launch message is its coverage line; a
  session never claims coverage it did not arm.** The launch-checklist memory becomes one line.
- CLAUDE.md hard convention "long-running jobs launch at low priority" → "launch through
  `anvil.runs`" (nice is the launcher's default).
- Tests: `tests/test_runs.py` (fast failure recorded, clean finish, stall → recovered → done, ack,
  the detached launch outlives the shell and prints coverage, wait / status).
- Routed: port the remaining register sites as each script is next used; wire
  `ANVIL_NOTIFY_CMD` to a phone channel for the user without the app (their choice of ntfy / mail);
  the first real launch through the launcher = the salted end arm (ADR-0106 C1 follow-up).

## Addendum 09-18 — the check-in moves INTO the supervisor (event-driven `claude -p`), a launch self-test, `--watch`, and `sweep` for dead supervisors

- **What failed on 09-17/18:** the post-Build-4 read chain finished at 00:39 and nobody learned it
  until 09:15. Every layer that ran did its job (the supervisor recorded every transition; the
  desk toasts fired); the consumer was missing: the scheduled check-in task had been disabled on
  09-16 (the "enabled only while runs are in flight" practice) and the launching session did not
  re-enable it or arm its own wait. The practice was the exact class this ADR retired for the
  session waiter — a step a session has to remember.
- **Decision (user, 09-18): the supervisor invokes the LLM itself.** On `failed`, `stalled` (at
  most once per 20 min), `gone` and `done` after > 1 h, `anvil.runs` runs a headless Claude Code
  session (`claude -p`, `--allowedTools` restricted to ToolSearch / ListAgents / SendMessage /
  PushNotification / Read / the ack command; the prompt on stdin) that pushes one notification,
  messages every interactive session on this machine whose name or title contains "anvil"
  (headless sessions register in the same local registry — verified: the desktop session
  appeared to a `-p` session under its title, the message arrived), acks the alert, and reports
  in one line. Its outcome is a `checkin` record in the queue (sinks off) — a consumer that did
  not run is visible next to the alert it missed. Off-thread; never touches the run's exit.
  `--checkin auto|claude|none` (auto = claude when the CLI is on PATH; `$ANVIL_CHECKIN` overrides).
- **The launch self-test.** Before the fork, `launch` runs `claude -p "Reply with exactly the
  word OK."` (3 s here). The coverage line ends with `check-in claude (self-test OK, 3 s)` or
  `check-in NONE — claude -p failed the self-test: <error>` plus a `checkin_unavailable` alert —
  the consumer's absence shows at the one moment someone is watching. On 09-18 morning the CLI's
  OAuth session had silently expired; this is the check that would have said so.
- **`--watch <glob>`** (repeatable): extra artifact roots for the stall tick. The read chain was
  launched from `data/runs/build4-alloc` while its arms wrote under `data/runs/b4post-*`, so a
  healthy read raised STALLED twice; `--watch 'data/runs/b4post-*'` names those roots. Chains
  that write elsewhere launch with it.
- **`sweep` / `install-sweep`** (the user's question: what if the run crashes completely?). The
  child's OOM kill is the ordinary case — the supervisor (small, nice 19, rarely the OOM
  victim) records `failed rc=-9` and checks in. The supervisor's OWN death (a reboot, an OOM
  that takes the session, kill -9) leaves a `running` state with a dead pid: `anvil.runs sweep`
  marks it `gone`, alerts with the log tail, and checks in; `install-sweep` puts it on a systemd
  user timer (every 10 min, persistent; `loginctl enable-linger` runs it before anyone logs in
  after a reboot) or prints the cron line elsewhere. The legacy `anvil_watchd` stays retired in
  place; the sweep is the launcher's own belt.
- **The scheduled task `anvil-run-checkin` is retired** (left disabled; its prompt in
  `docs/ops/run-checkin.md` stays as the fallback for a machine with the app but no CLI).
- **Verified end to end 10:23 09-18:** a deliberately failing launch → the self-test (3 s) → the
  failure → the headless check-in in 15 s: pushed, messaged the supervising session (the relay
  arrived in it), acked. The first attempt found a real bug (the prompt passed positionally after
  the variadic `--allowedTools` was swallowed — the `checkin` record said so; fixed to stdin).
- Tests: `tests/test_runs.py` +5 (a `claude` shim on PATH: the failure check-in + its record, no
  check-in on a short done, one check-in per flapping stall, the failed self-test downgrading to
  none with its alert, the sweep marking gone + checking in, `--watch` keeping a chain from
  false-stalling). The test fixture pins `ANVIL_CHECKIN=none` so no test reaches the real CLI.
- Standing rule (amended): the launch's coverage line names the check-in consumer; a session
  still arms its own background wait (the belt under the belt).
