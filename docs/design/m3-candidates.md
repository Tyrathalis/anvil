# M3 candidates — pre-planning list

2026-07-17. Deliberately light: this is the menu for the dedicated M3
planning session (fresh context), not the plan. M2's arc was "RL machinery
end-to-end"; the M3 north-star question is on the table below. Inputs: all
four M2 done-whens resolved (ADR-0019), run-3 veto forensics
([run3-veto-forensics.md](run3-veto-forensics.md)), the #ai-plotting thread
(manabrew/khaliostr reply + Hanmac's offer, 2026-07-16/17), community
archaeology ([discord-ai-plotting-survey.md](discord-ai-plotting-survey.md)
+ dives), and the standing upstream worklist.

## Track A — RL science (the strength program)

- **Veto drift, cause-first**: commander-tax observation gap (73% of
  commander vetoes are post-first-cast — likely a feature fix, not reward
  shaping; check obs derivability → no corpus regeneration). Then the
  general levers: small reward veto penalty (§3d pin required),
  first-attempt veto rate as the monitor metric, per-head entropy floors
  (Austinio-validated), X-inclusion refinement.
- **Scale under guards**: run-3 stopped for a fixable reason at 13
  iterations; with the veto cause addressed, push iterations (the loop is
  stable, guarded, and ~45 min/iteration). Where's the ceiling of the
  current recipe?
- **Full-vis critic in the loop** (documented D6 upgrade): doubles
  target-pass cost; justified when the masked head becomes the binding
  constraint.
- **Rollout value labels at scale**: machinery certified + priced in D4;
  micro-batching largely built since — re-price.
- **Ante correctness items**: draw-poison coverage (69%), re-deal
  re-anchoring, node-level draw bias — all queued "with the critic
  upgrade."
- **Grindstone seeding (§6)**: the 34 never-cast blind-spot cards + drill
  economy first steps; provenance machinery exists.

## Track B — Upstream / engine (the community moment)

- **Determinism-hooks collaboration with manabrew** (khaliostr: "very keen",
  proposes a joint Forge-tracker issue; their patch `d658cbc757` =
  ThreadLocal MyRandom + sorted pre-shuffle + resetIdCounter + image-cache
  reclaim). **Hanmac (maintainer) offered per-Game ID counters** — better
  than the static reset, and obsoletes part of both forks. Our survey rule
  ("design conversations in PRs/Discord, not issues") suggests steering
  toward a draft PR early. Caveat carried from archaeology: their
  Fireball/Officious SVar fix didn't verify as stated — sim-test before
  co-signing.
- **#11161 fork rebase** = the dataset-boundary event: folds in our merged
  #11203 fixes, the `thisTurnCast` rework, the pre-shuffle determinism fix,
  and whatever the joint PR lands. Sequencing question: rebase before or
  after the next big corpus/RL push?
- **endstep concurrency patches** (Neur0nz; manabrew PR #493 reports "very
  good" improvement): statics → ThreadLocal, true concurrent games in one
  JVM. Could reshape worker economics (8×2g JVMs → threads; RAM and
  startup amortization; crash isolation trade-off vs our chunk mechanism).
  Evaluate, don't assume.
- **GameCopier→GameSnapshot consolidation follow-up** (maintainer-blessed
  since #11203; manabrew is a live snapshot-restore consumer = supporting
  evidence).
- **manabrew protocol v1 review** (their PR #445; they explicitly invited
  gap-flagging). Interop is optional; goodwill + a real look at whether
  their backend protocol and our bridge could converge long-term.

## Track C — Expressiveness / format

- Mode heads (1.2% mass), yield macros (parked since M1), divided/alloc
  (0.03%).
- AR combat decoder (documented D5 upgrade path).
- Pool breadth per ADR-0018 roadmap rule: precon chunk queued
  post-core-features; ID dropout = the pre-Tutor zero-shot lever
  (unproven, needs its demonstration experiment).

## Track D — Infrastructure QoL

- VRAM elasticity (task #12 spec: per-phase seg autotune + OOM-retry).
- Single-JVM workers if endstep patches evaluate well (Track B).
- Monitor/babysit polish: first-attempt veto metric, guard-halt push
  notification from the driver itself.

## The framing question for the planning session

M2 proved the loop improves the policy. M3's identity choice: **strength
program** (Track A dominant: push winrate well past the teacher, Grindstone
online) vs **platform round** (Track B dominant: rebase + upstream
collaborations while the community moment is hot, RL continues at
maintenance pace) vs a split. The Discord thread's timing argues for at
least the joint determinism PR landing early regardless.
