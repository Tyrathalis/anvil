# The run check-in (ADR-0107): the fallback prompt

**Doc status:** reference · the fallback for a machine with the desktop app but no authenticated `claude` CLI. On
every other machine the launcher runs the check-in itself and nothing here is installed.

## What runs by default

The run launcher's supervisor (`anvil.runs launch`, [anvil/runs.py](../../anvil/runs.py)) answers its own alerts.
The [quickstart, §7½](../design/quickstart-custom-pool.md) is the operator's guide to it; this is the summary.

- **When it fires.** On `failed`, `stalled`, and a `done` after more than an hour, the supervisor runs one headless
  `claude -p` session with read-only tools. The sweep (`anvil.runs sweep`, on a ten-minute user timer after
  `anvil.runs install-sweep`) does the same for a run it marks `gone` or `orphaned`. A stall that flaps raises at
  most one check-in per 20 minutes. A run stopped with `anvil.runs pause` records `paused` and raises none.
- **What it does.** It pushes one notification, messages one Claude Code session and acks its own alert. The
  session is the one whose ListAgents row carries the bracketed ref recorded by `--launched-by '<name> [<ref>]'`
  (`relaunch --launched-by` re-points it). With no match, it is the newest session whose title contains "anvil".
  The message tells any other reader not to write the run's close: the launching session owns it.
- **How you know it is armed.** `--checkin auto` (the default) uses `claude` when the CLI is on the path. The
  launch and every `relaunch` run a self-test, and the coverage line reads `check-in claude (self-test OK, N s)` or
  `check-in NONE — ...`. `--checkin none` turns it off; `$ANVIL_CHECKIN` overrides the flag.
- **What it watches.** The stall tick reads the newest file under `--dir` and under every `--watch <glob>` root,
  which is how a chain whose arms write elsewhere stays covered. `heartbeat.json` holds the alarm off during a
  deliberate wait.
- **States it reports.** `gone` is a dead supervisor with nothing of the run alive; under `--resume-on-gone` the
  sweep relaunches such a run, up to `--resume-max` times. `orphaned` is a dead supervisor over a live command: the
  sweep alerts once and starts nothing, and `launch`, `relaunch` and `pause` refuse the run until its command has
  stopped. `anvil.runs wait --name N` exits 0 done, 1 failed, 2 gone, 4 paused, 5 orphaned.
- **A loop's wall budget** is the loop's own flag, `selfplay.py --wall-hours`: the loop stops between iterations,
  the command exits 0 and the run reads `done`.

## The fallback

Without the CLI the coverage line reads `check-in NONE` and the alert queue still records every event. Two ways to
drain it:

- Paste the block below as the prompt of a desktop-app scheduled task (Claude Code → scheduled tasks), every
  30 minutes. Enable it while runs are in flight and disable it when the last one lands. The app owns that switch,
  so this is a practice and not code. The project's own task of this kind, `anvil-run-checkin`, is disabled.
- Or run `uv run python -m anvil.runs alerts --unacked` from any cron and pipe it to your own channel.

The prompt is read-only by design: it reports and never fixes. Replace `<repo>` with the path of your Anvil checkout.

---

You are the Anvil run check-in. You are read-only: never edit files, never kill or launch
processes, never try to fix a run. Work in `<repo>`.

1. Run `uv run python -m anvil.runs alerts --unacked --json` and `uv run python -m anvil.runs status`.
2. If there are no unacked alerts and no run is `stalled`, `gone` or `orphaned`: stop. Say nothing to anyone.
3. Otherwise, for each unacked alert (and each `gone` or `orphaned` run with no alert, which is one the sweep
   has not visited):
   - Read the last 30 lines of the run's log (the `log` field) so the message names the actual
     error, not just "failed".
   - Send ONE push notification per run, under 200 characters, leading with what to act on:
     `<run> FAILED rc=1: <first error line>` / `<run> STALLED 95 min: newest <file>` /
     `<run> DONE in 6.2 h` (done alerts: push only if the run took longer than an hour).
   - Read `launched_by` in the run's state file (`~/.local/state/anvil/runs/<run>.json`). Call ListAgents
     and send ONE message to the session whose row carries that bracketed ref; if none does, to the newest
     session whose title contains "anvil". The message: the alert kind, the run name, the state file, the
     log path and the error lines, then: "The session that launched this run owns its record; if you are
     not that session, do not write its close." Do not ask it questions.
4. Ack what you reported: `uv run python -m anvil.runs ack --id <id>...`.
5. End your run with one line per alert handled. Nothing else.
