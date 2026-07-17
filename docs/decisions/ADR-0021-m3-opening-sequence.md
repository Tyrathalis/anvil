# ADR-0021: M3 opening sequence — split milestone, RL spine, rebase closes

- **Date:** 2026-07-17
- **Status:** accepted (seeds [m3-plan.md](../design/m3-plan.md), per the M1/M2 pattern)
- **Design-doc anchor:** §3d (reward pins), §6 (RL/Grindstone), §9 (fork discipline); ADR-0017 (guards), ADR-0018 (features-before-breadth), ADR-0019 (veto-drift levers), ADR-0020 (M2 closeout)

## Context

M2 closed with all four done-when clauses resolved (ADR-0020): the guarded
V-trace loop improves the policy past its teacher (+6.75pp ± 2.31 corrected,
ADR-0019). [m3-candidates.md](../design/m3-candidates.md) framed the milestone
identity question: strength program vs platform round vs split.

Two inputs resolved it in the 2026-07-17 planning session:

1. **The veto-drift cause candidate is sharp.** Iter-013 forensics
   ([run3-veto-forensics.md](../design/run3-veto-forensics.md)): 76% of vetoes
   `unpayable`, 73% of commander vetoes post-first-cast — the observation
   lacks commander tax, so the policy prices recasts at printed cost. A
   feature fix, likely reader-side derivable, sits ahead of every
   reward-shaping lever.
2. **The community moment got hotter than planned.** The #ai-plotting
   introduction (posted 2026-07-16) drew khaliostr/manabrew's collaboration
   enthusiasm within hours, and maintainer Hanmac filed
   [forge#11260](https://github.com/Card-Forge/forge/issues/11260) (per-Game
   ID counters; self-assigned + tool4ever + MostCromulent) the next morning —
   the determinism centerpiece is now maintainer-led upstream. Same session:
   manabrew's Fireball SVar claim was probed and does not reproduce
   (`FireballRaiseCostTest`, fork `023e8c5da9`) — excluded from any joint PR,
   setting the every-claim-carries-a-test precedent.

## Decision

User decisions 2026-07-17:

1. **M3 identity: split, with the RL spine dominant.** Veto-cause fix →
   guarded scaling is the ordered spine; the upstream track (joint
   determinism PR, #11260 support, #445 review, endstep evaluation) runs
   parallel at community pace and never blocks the spine.
2. **The #11161 fork rebase is M3's closing dataset-boundary event.** Land
   the determinism work upstream first; one rebase folds everything back
   (#11203 fixes, `thisTurnCast` rework, pre-shuffle sort, per-Game
   counters). The fork stays pinned through all M3 RL runs; the
   trajectory-changing pre-shuffle sort lands fork-side only at this
   boundary.
3. **Grindstone is the flex slot** (D5-in-M2 pattern), seeded by the 34
   never-cast blind-spot cards; no done-when clause.

Plan-level pins (consequences in [m3-plan.md](../design/m3-plan.md)):
cause-first veto work with reward penalty/entropy floors held in reserve
behind a counterspell-hold examination; #11260 supported not implemented;
endstep concurrency evaluated with the failure path tested, not assumed;
Track C expressiveness out unless RL telemetry indicts; ADR-0017 guards,
Ante-corrected milestone reads, and the BC-ckpt forkcheck gate carry
unchanged.

## Consequences

- The M2 pre-RL scope rule gets its M3 successor: work enters the spine only
  through veto-cause evidence, guarded-scaling results, or eval sharpness —
  upstream goodwill is real but budgeted as the parallel track.
- Done-when clauses (full wording in the plan): (1) veto cause resolved on
  fresh-RL forensics + first-attempt veto ≤ D5 baseline; (2) a guarded run
  beats iter-012 outside noise at the 2,000-game corrected read; (3) the
  committed upstream surface submitted with tests + forkcheck verification,
  #445 gap list delivered; (4) rebase complete, gate green, fork-local
  copies dropped.
- Risk accepted: community latency and #11260 design drift are outside our
  control; the early design-input comment and forkcheck verification are the
  mitigations, and the spine proceeds regardless.
