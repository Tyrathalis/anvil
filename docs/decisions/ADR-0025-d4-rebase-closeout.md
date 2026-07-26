# ADR-0025: D4 rebase closeout — the fork is current, and the agent is back at parity with a stronger heuristic

Date: 2026-07-26
Status: accepted

## Context

M3 D4 was scheduled as the milestone's closing act: the dataset-boundary
rebase that folds our merged #11203 fixes back in from upstream, picks up
the 07-24 determinism convergence (#11360/#11358/#11365), lands the
pre-shuffle sort fork-side, and re-baselines everything on the new engine.
The fork had been pinned at `0bfdaa572f` since 2026-07-02 — 237 upstream
commits of drift, 26 of them touching `forge-ai/`, i.e. the heuristic that
is simultaneously our corpus teacher and our arms opponent.

## What was done

**Pin choice.** Rebased onto `3e3818f1ba` (last 2026-07-24 commit) rather
than upstream tip. That captures the whole determinism dividend while
excluding 17 same-day commits including a landed-and-reverted AI change
(#11379/#11391) and a 3-hour-old AI behavior change (#11388). Rationale:
whatever we pin becomes the teacher and opponent for the entire M4 era, and
pinning bleeding-edge AI churn buys nothing.

**Mechanics.** 28/28 commits replayed with zero conflicts; `42e15f4822`
(GameCopier fidelity) dropped explicitly — #11203 came home byte-identical,
so `GameCopier.java`, `Game.java` and `Player.java` left the fork diff
entirely. The determinism-hooks commit (`f4fc37db3e`, the #11285 surface)
cherry-picked clean. The fork's entire engine delta is now **14 lines in two
files** (`AiController.removeUnpayableAttackers` made public;
`PhaseHandler.devResumeAtPriority`) plus Anvil-only files. Old tip preserved
as tag `pre-rebase-20260725`; `master` reset (rebase rewrites history — not
a fast-forward).

**Gates.**

| gate | result |
|---|---|
| Java suite | 292 green |
| Python suite | 98 green |
| `forkcheck -twin` (200 games, paired seeds vs 07-10 baseline) | divergence **16.5% → 7.0%**; chain 2/200 → 1/200; 0 statics |
| `forkcheck -grpc` smoke (BC ckpt) | 10/10 clean, 0 statics, 0 transport |
| `forkcheck -twin -grpc` (BC ckpt) | **twin determinism 40/40**, 0 statics, 0 fallbacks |
| pool cards resolve | 1,701/1,701 |
| pool census (heuristic, 113 decks, 120 games) | 120/120 decisive; turns median **21 vs 21**; callbacks/game **1,117 vs 1,136** |

The copy-fidelity divergence more than halving is the #11360 dividend
landing where the worklist predicted. Certification used `d5-combat`
(current BC ckpt of record) rather than 07-10's `d7-ep3`, so the gate also
exercises the combat heads — a strictly stronger gate than the original.

**The connive regression.** Upstream `28431f2647` ("Recruit: add Effect",
#11355, 2026-07-24) changed `ConniveEffect` to hand `discard()` an immutable
`Map.of(...)`, but `SpellAbilityEffect.discard()` writes the post-move
collection back into that map (`:906`) so its own `DiscardedAll` loop can
read it. Every connive resolution throws `UnsupportedOperationException`;
the new `RecruitEffect` shipped with the identical bug. **The rebase
inherited it**, and it cost a full 4,000-game arms read: 28 crashes in 2,000
games (1.4%) against 4 in all pre-rebase history, concentrated in the five
pool decks carrying connive cards (Illuminator Virtuoso, Ledger Shredder,
Lethal Scheme) — a per-matchup bias, not uniform noise. Fixed fork-side at
both sites (mutable map), pinned by `ConniveDiscardMapTest`, validated
failing first. Post-fix: **0 UOE in 2,000 games**. Deliberately NOT
upstreamed — Hanmac took responsibility for the regression; no caller of
`discard()` reads the map back, so every plausible maintainer fix is
behaviorally identical to ours (see the exemption below).

## The measurement that matters

Four 2,000-game Ante-corrected reads, `final_read` protocol, 8 workers each,
run sequentially so the heuristic's wall-clock timeouts saw identical load:

| | old engine | new engine | Δ (new − old) |
|---|---|---|---|
| **RL** `d6-run7b/iter-014` | 0.5530 ± 0.0109 | **0.5121 ± 0.0110** | **−4.09 ± 1.55** (t = −2.64) |
| **BC** `d5-combat` | 0.4616 ± 0.0109 | **0.4452 ± 0.0109** | −1.64 ± 1.54 (t = −1.06) |

- **RL over BC survives the engine change robustly: +6.69pp ± 1.55
  (t = +4.32)** on the new engine, versus +9.14pp on the old. The central
  M2/M3 claim — that the RL work produced a genuinely stronger policy than
  the imitation baseline — holds.
- **Against the heuristic, the agent is now at parity: +1.21pp ± 1.10
  (t = 1.10)**, where the old engine read +5.30pp (t = 4.86).
- **Difference-in-differences (is the extra RL drop real?): −2.45pp ± 2.19,
  t = −1.12 — NOT significant.** The control was run to separate "uniform
  environment shift" from "RL-specific regression" and it does not resolve
  that question: stacking two differences inherits SE 2.19pp. Recorded as a
  planning error — the power calculation belonged before the runs, not
  after.

**Leading explanation: the heuristic got stronger** (26 `forge-ai` commits;
the maintainers have been actively tuning AI behavior). Consistent with the
direction of both drops and with BC's first-attempt veto rate *falling*
(0.1395 → 0.1072), i.e. action realization got easier, not harder — the
opponent plays better, our actions don't land worse. A second, unexcluded
mechanism: a policy trained against a specific opponent has more
opponent-specific fit to lose than an imitation policy does (the §6d
mirror-overfit family). The point estimate is consistent with both; the
statistics establish neither.

## Decisions

1. **D4 CLOSED. M3 done-when #4 SATISFIED** (rebase complete, gates green,
   fork-local #11203 copies dropped). All four M3 clauses are now resolved;
   M3 closeout is the next session-level decision.
2. **RL checkpoint of record UNCHANGED**: `d6-run7b/iter-014/train/last.pt`.
   It is still +6.69pp over BC; only the reference point moved.
3. **The headline claim is restated, not re-scaled.** ADR-0019's and
   ADR-0023's "first teacher-surpassing read / ~2σ better than the heuristic
   it imitated" was measured against the *old* heuristic. **On the current
   engine the agent is at parity with the heuristic.** Every pre-rebase
   winrate — including the early-doom ceiling figures (0.826/0.920) — sits
   on the old scale and is not comparable to post-rebase reads.
4. **Fork-discipline convention amended.** "Engine upgrades are dataset
   boundary events" gains an exemption: a change that is *behavior-identical
   on the game path* is not a boundary, and the burden of proof is
   **empirical, not argued** — same seed set on both jars, identical
   `forkcheck` trace hashes (~15 min for 40 seeds). Any mismatch ⇒ boundary.
   Scope note: a crash fix never qualifies (the connive fix turns a crash
   into a resolved connive, which is why the contaminated read was
   discarded); replacing our fork-local fix with an upstream fix of the same
   defect does. Adopted by the user 2026-07-26; `CLAUDE.md` hard-conventions
   line updated to match.
5. **Do not chase the difference-in-differences.** Resolving −2.45pp at
   t = 2 needs ~8,000 games/cell (~16h) and changes no decision. The
   forward-looking question — does the recipe still gain on the new engine —
   is answered by the next guarded run, which is wanted regardless.

## Consequences

- Every RL run from here is on `master` @ `5fbc2ac98d` (upstream
  `3e3818f1ba` + 30 Anvil commits). Pre-rebase runs stay on
  `pre-rebase-20260725`; no mixing.
- **Expect a conflict on the connive lines at the next rebase and DROP OURS**
  in favour of upstream's fix, the way the #11203 copier fixes came home.
- The M4 planning baseline is 0.5121, not 0.5530. Any "beats the heuristic"
  target must be re-derived on the new scale.
- Open, carried forward: the `IndexOutOfBoundsException` class (2 crashes in
  the RL read, both deck `dc-863943`, both early, both seed-pinned — a
  replay with `-Danvil.crash.trace` is the check, and is a plausible upstream
  filing candidate); `final_read.py` riders (notify hook lifted from the
  selfplay driver, stdout line-buffering, `pool_version` provenance — its
  ingest warns "provenance is incomplete" today); the pool-manifest
  mtime-selection hazard (`latest_pool_manifest()` picks by mtime; `pool
  status` and the harness disagree on which manifest is "latest").

## Method notes worth keeping

- **A crash class is a stack trace, not an exception type.** The first
  connive crash was dismissed as pre-existing because
  `UnsupportedOperationException` had 4 historical occurrences. It was new.
  That shortcut cost a 4,000-game read; the bug was only found because the
  user asked whether the pool contained connive cards.
- **Verify the instrument before trusting a gate.** The first "pool smoke
  gate" ran `--bridge local-random` (the harness default) instead of the
  heuristic, and `--workers 8` silently gave one worker because
  `chunk=200 ≥ 120 games`. Its alarming numbers (median 48 turns, heap OOM)
  were properties of the random arm. The `forge census` re-run was the
  correct instrument and has a recorded baseline to compare against.
- **Arm the watcher in the same action as the launch.** Two ~2h reads were
  launched detached with no watcher, so completion reached nobody and the
  user had to ask. Key watchers on the output artifact with a liveness check
  inside the loop, so a crash that never writes the artifact still pings.
