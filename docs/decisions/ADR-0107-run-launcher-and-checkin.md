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
