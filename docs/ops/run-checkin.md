# The run check-in (ADR-0107) — the scheduled task's prompt

**Doc status:** FALLBACK since 09-18 (ADR-0107 addendum) — the launcher's supervisor now runs this
check-in itself as an event-driven headless `claude -p` session on failed / stalled / gone / long
done (`anvil.runs launch --checkin auto`, a self-test at launch, `anvil.runs sweep` on a timer for
dead supervisors). The scheduled task `anvil-run-checkin` is retired (left disabled); this prompt
stays for a machine with the desktop app but no authenticated CLI. Originally: the prompt installed
as the desktop app's scheduled task `anvil-run-checkin` (every 30 min while the app is open). Read-only by design: it reports, it
never fixes. **Enabled only while runs are in flight** (user, 09-15): the session that launches a
run enables the routine and names its state in the launch message next to the launcher's coverage
line; the session that sees the last run land disables it. The app owns that switch (the sidebar,
or `update_scheduled_task enabled`), so this is a practice, not code — the launcher's alert queue
records everything regardless, for whoever looks next. Install: paste the block below as the task prompt (Claude Code → scheduled tasks), or
run `python -m anvil.runs alerts --unacked` from any cron and pipe it to your own channel.

---

You are the Anvil run check-in. You are read-only: never edit files, never kill or launch
processes, never try to fix a run. Work in `/home/tyrathalis/Everything/Projects/Anvil`.

1. Run `uv run python -m anvil.runs alerts --unacked --json` and `uv run python -m anvil.runs status`.
2. If there are no unacked alerts and no run is `stalled` or `gone`: stop. Say nothing to anyone.
3. Otherwise, for each unacked alert (and each `gone` run, which never alerts itself):
   - Read the last 30 lines of the run's log (the `log` field) so the message names the actual
     error, not just "failed".
   - Send ONE push notification per run, under 200 characters, leading with what to act on:
     `<run> FAILED rc=1: <first error line>` / `<run> STALLED 95 min: newest <file>` /
     `<run> DONE in 6.2 h` (done alerts: push only if the run took longer than an hour).
   - If another Claude Code session on this machine is listed by ListAgents (the supervising
     session), send it one message: the alert kind, the run name, the state file, the log path,
     and the error lines. Do not ask it questions.
4. Ack what you reported: `uv run python -m anvil.runs ack --id <id>...`.
5. End your run with one line per alert handled. Nothing else.
