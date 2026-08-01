# ADR-0029: D3 experiment (a) resolution — drill mixing at f=20% is strength-neutral with a diagnosed transfer asymmetry

Date: 2026-08-01
Status: accepted
Context: M4 D3 (m4-plan), d6-run10 (first drill-mixed run), ADR-0027/0028.

## Result

d6-run10 (standing recipe + drill phase: 15 selected points × K=8 sampled
completions/iter = 20% of fresh games, mainline pinned run9-i009, init
run9-i009) ran 16 accepted iterations, then **guard-halted at iteration
16 on a genuine multi-signal drift** (KL 0.085 > 0.06; census
first-attempt veto 0.154 marginally past its own 1.5× line; entropy off
its floor). The ADR-0017 machinery worked as designed.

**2,000-game Ante-corrected paired reads (seeds 20260710):**

| comparison | corrected | paired Δ | t |
|---|---|---|---|
| iter-004 vs baseline 0.5121 | 0.5254 ± 0.0110 | +1.40pp ± 0.96 | 1.46 |
| iter-015 vs baseline 0.5121 | 0.5273 ± 0.0109 | +1.45pp ± 1.04 | 1.39 |
| iter-015 vs run9-i009 (init) | — | +0.25pp ± 1.06 | 0.24 |
| iter-015 vs iter-004 | — | +0.05pp ± 1.00 | 0.05 |

**The promotion gate is NOT cleared** (directionally-positive ties vs
baseline, same magnitude as run9's +1.15). The sharper facts are the two
flat rows: 16 drill iterations bought nothing over the run's own init,
and the dose-response between 4 and 15 drill iterations is exactly flat.
Checkpoint of record unchanged (`d6-run7b/iter-014`); the 0.5121
baseline stands.

## But the drill signal was learned — and the eval decomposition says where it went

Held-out drill evalset (176 drills the training list never contained),
paired per the D2.4 protocol against the pinned policy's re-measurement:

| bin | iter-004 | iter-015 |
|---|---|---|
| lost | +0.0pp | **+6.6pp** (~2.5σ) |
| long_shot | −1.0pp | **+6.7pp** (~2.5σ) |
| coin | −3.2pp | −0.7pp |
| winnable | −4.9pp | **−9.7pp** (~5σ) |

Play-from-behind improved on UNSEEN hard positions — generalization, not
memorization — and grew with drill dose. But it came with an
equal-and-opposite regression at converting won positions, netting ~zero
at the drill pool and ~zero at full games.

**The distribution artifact behind it:** the evalset stratification
(D2.4) held out the ENTIRE winnable and coin bins (all 66 + all 50), so
the training drill list was ~100% behind-positions *by construction*.
The mixture taught fighting from behind with zero ahead-play
counterweight. The winnable regression is what that mixture should be
expected to produce.

**Guard-halt mechanism (consistent, not fully proven):** drill
trajectories carry 1.65× the rejection density of full games (2.44 vs
1.48 events/100 windows at iter-15) — sustained extra §6c penalty
gradient — and the shaped-vs-masked anomaly gap grew monotonically from
iteration 12 until the halt; by iteration 16 the veto drift was visible
in full-game census too (0.10 → 0.15). Run-3's veto-drift class,
plausibly accelerated by the drill mixture's penalty density.

## Incidents absorbed en route (both now structural)

- The iteration-9 driver crash: wedged completions (targeting-retry
  hang, ~1 GiB obs, RAW_CAP fired) → hard-cap thread abandonment → the
  abandoned thread killed the shared fork-file fd → one truncated frame
  killed ingest → killed the driver. Fixed at all three layers (fork
  `7249a41b60`: owner-bound fork frames + wire-only fallback for
  orphaned threads; Anvil `eb6381f`: quarantine ingest). The identical
  wedge recurred at iteration 9's re-run and cost exactly one
  quarantined frame. Hang-class forensics queued (upstream-worklist).
- Watcher/notification post-mortem: every alert fired but reached only
  an unattended desktop; the `pgrep -f` self-match class bit three
  separate babysitters. Standing systemd watcher (`anvil_watchd`) now
  registration-file + (pid, starttime, btime) based; phone channel
  pending user's KDE Connect setup.

## Decision

1. **Experiment (a) at this configuration: resolved strength-neutral**,
   recorded here to the negative-result standard. No full-game gain, no
   full-game cost, real but self-cancelling drill-context learning.
2. **The mechanism licenses one bounded (a)-refinement before
   escalating to (b):** the flat result is confounded by an avoidable
   mixture artifact (zero ahead-positions) and a diagnosed stability
   pressure (drill-side §6c density). A rebalanced run — evalset
   re-split to hold out a stratified *fraction* per bin instead of
   whole bins, training mixture carrying ahead-positions at meaningful
   weight, plus optionally a drill-side penalty basis — tests a crisp
   hypothesis: *the winnable regression was the balancing term; fixing
   the mixture converts hard-position gains into net strength.*
3. Whether to run (a2) or escalate directly to (b) K-rollout advantage
   baselines is a milestone-direction call — put to the user with this
   ADR. The escalation ladder itself is unchanged.

## Consequences

- `drill-evalset-v1` is superseded for training-adjacent use: any
  future selection must re-split so training keeps ahead-positions.
  (The evalset remains valid as a measurement instrument.)
- Per-source rej/veto splits join the monitor's watch basis informally
  (the shaped-vs-masked flag fired 4 iterations before the halt — it
  was the right early warning, now with a validated interpretation).
- run10 candidate ckpts are kept (iter-015 = the behind-play-enriched
  policy; a future curriculum-mixture run may want it as an init or
  contrast).
