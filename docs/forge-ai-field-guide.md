# A field guide to building learned agents on Forge

Anvil is a neural MTG agent built on a Forge fork ([README](../README.md),
[design doc](design/anvil-design-v2.md)). Along the way we hit — and measured,
and in several cases fixed upstream — a set of traps that we've since watched
other Forge-AI projects rediscover independently (see the
[community survey](design/discord-ai-plotting-survey.md)). This guide is the
short version: each trap, how it bites, how to detect it, and what we did,
with pointers into our ADRs and code. Everything here is measured, not
theorized; numbers link to their records.

If you only take five things:

1. **Never read a bridge/model answer without checking its fallback flag** —
   silent fallback to the heuristic poisons both your corpus and your evals.
2. **Log decisions, options, and observations at generation time** — Forge
   games do not replay deterministically enough to recompute them later, and
   asking the engine "what would you do" mid-game has side effects.
3. **Your winrate eval needs ~10× more games than you think** — 95% CI is
   ±2.2pp at 2,000 games. Most "improvements" under 400-game evals are noise.
4. **The AI code path is omniscient** — if you train on what
   `PlayerControllerAi` can see, your model trains on hidden information
   unless you enforce the information set yourself, in one tested place.
5. **`GameCopier` was unfaithful until 2026-07-12** — if you fork game states
   for rollouts/MCTS on a fork pinned before upstream merge `1922ce411a`
   ([#11203](https://github.com/Card-Forge/forge/pull/11203)), your copies
   renumber card ids and corrupt state at measurable rates. Rebase, or
   cherry-pick the fixes.

---

## Engine and harness

**Forge decision callbacks fire during legality/payability probing.** The
engine calls real `PlayerController` methods while *testing* whether something
can be paid or played (`CostAdjustment`, `ComputerUtilMana`, auto-pay). If
your controller treats every callback as a real decision — or consumes RNG in
one — you'll desync, double-count decisions, or perturb the game. Related:
scanning the AI's own availability logic to enumerate options is **not a pure
observer** — we measured 6/20 same-seed games diverging with the option scan
on vs off. Consequence: **legal options must be captured at generation time by
the process that plays the game**, not recomputed afterward and not probed
from outside. ([ADR-0005](decisions/ADR-0005-d3-label-mask-semantics.md),
[bridge protocol](design/bridge-protocol-v0.md); manabrew handles the same
class with a `probingPayability` flag.)

**Games crash, hang, and wedge at a low floor — design for it.** Across 50K
games we saw ~0.5% non-decisive outcomes: engine crash classes (most are
thread races, since fixed upstream in #11161), draw-clock grinders, and one
OOM class where the default handler pops a *modal bug-report dialog* in a
headless worker (fix: an uncaught-exception handler + `Throwable` catches +
`-XX:+ExitOnOutOfMemoryError`). Our harness treats workers as disposable:
200-game chunks, seeded game-granularity resume, zero-progress abort guards,
per-run pinned jar hash. Every other project we surveyed converged on a
supervisor-kills-stuck-workers design; ours is spec'd in
[m0-batch-harness-spec.md](design/m0-batch-harness-spec.md).

**State copying (`GameCopier`) had three measured bug classes.** At M0 we
found 50% of forked games diverging deterministically and 12% failing static
state comparison ([ADR-0002](decisions/ADR-0002-fork-api-gate-resolution.md));
root causes were card-id renumbering plus two static corruption classes
(face-down exile leak, effect-card field wiring). Fixed upstream in
[#11203](https://github.com/Card-Forge/forge/pull/11203) (merged 2026-07-12);
post-fix, statics are 0% and divergence drops to 2.5% under a model policy
(residual = this-turn field copy gaps, characterized). Two things to know if
you fork states: (a) `GameCopier.clonePlayer` silently swaps non-AI-derived
controllers to the heuristic AI on copy — derive your controller from the AI
lobby player or your forked games play themselves with the wrong policy;
(b) copy fidelity regresses — we keep a standing regression harness
(`forkcheck`: digest comparison + twin determinism + full-gate-under-model)
and run it on every engine bump ([ADR-0011](decisions/ADR-0011-d1-closeout.md),
[fork-fidelity-test.md](design/fork-fidelity-test.md)).

**Determinism is a set of separate surfaces; enumerate them.** Seeding
`MyRandom` is necessary, not sufficient. Surfaces we've measured or patched:
RNG capture/restore around forks; deterministic construction ordering;
hash-ordered iteration in AI decision paths (worth ~1% twin divergence at
heuristic decision rates — amplified 40× under random policies); an unseeded
`Collections.shuffle` in smoothed-hand logic (upstream has since moved
gameplay shuffles to `MyRandom`); and — found via manabrew's parity work —
**pre-shuffle library order is `CardPool`'s ConcurrentHashMap iteration
order**, i.e. stable only per-JVM-version. Pin your JVM and your fork per run
(a manifest with jar hash; workers refuse on mismatch), and treat engine
upgrades as dataset boundary events.
([upstream-worklist.md](design/upstream-worklist.md) tracks the joint
determinism-hooks upstream PR.)

**The AI code path is omniscient, and the engine never validates AI combat.**
`PlayerControllerAi` reads whatever it likes off the `Player`/`Game` objects —
train against that surface and your model sees opponent hands and library
order. We serialize full-state records with per-entity visibility and enforce
the information set in exactly one leak-tested Python transform, shared
byte-identically between training and serving
([observation-schema-v1.md](design/observation-schema-v1.md),
`tests/test_serve_parity.py`). Separately: `CombatUtil.validateBlocks` is
called for *human* input only — an AI-path controller can declare
rules-illegal blocks and the engine plays on silently. If you emit your own
blocks, you must run the requirement fixed-point (`mustBlockAnAttacker`)
yourself ([ADR-0016](decisions/ADR-0016-d5-closeout.md)).

**Costed vetoes are your action space leaking away.** The heuristic's
`canPlaySa` applies *judgment*, not just legality — routing a learned policy's
choices through it vetoed 65% of casts in our first controller. Our realizer
enforces legality only ([ADR-0009](decisions/ADR-0009-m1-closeout.md), veto
65%→3–8%), and vetoed decisions **re-ask** the model with the vetoed candidate
removed, so a veto becomes a model-chosen alternative rather than a silent
forced pass the reward never sees. Austinio's project observed the same leak
from the outcome side: losses had 29% "idle turns with castable spells."

## Data and labels

**Check the fallback flag. Always.** Every answer over our bridge carries
provenance (`bridge` vs `heuristic-fallback`), evals gate on zero fallbacks,
and the serve path never silently substitutes. This isn't hypothetical
paranoia: another project's headline "54% parity with the heuristic" turned
out to be the heuristic playing against itself behind a dead model-server
flag, and their RL trajectories contained heuristic decisions labeled as
model decisions ([survey dive](design/survey-dive-austinio-rl-branch.md)).

**Validate outcome labels against a second source.** Our serialized
`end.winner` was a post-elimination live-list index — wrong ~50% of games —
so every value head we trained before the fix learned *seat noise* while all
policy metrics looked healthy
([ADR-0013](decisions/ADR-0013-winner-label-poisoning.md)). The fix included a
validator that cross-checks the winner against an independent record
(final life totals). If you have two representations of the same fact,
cross-check them; if you have one, make a second.

**Split train/val by game (and by deck pair), not by row.** Decisions from
one game are near-duplicates; if any leak across the split, your accuracy is
inflated (a surveyed project measured 95%→80% on fixing exactly this — and
then found the same bug in three more places, including "one file per player"
splits that still leak the game). Ours are deterministic hash splits by game
index, with a second held-out-*matchup* split (`valpair`) to detect
memorization of deck pairings.

**Trajectory storage: ~47KB/game is achievable.** Full-state observation
records at every decision, JSONL in zstd frames, ~70–95× compression; 113,592
games ≈ 5GB. (For contrast, a JSON+numpy pipeline we surveyed runs ~65MB/game
— 260GB for 4K games — and disk I/O became their training bottleneck.)
Schema in [observation-schema-v1.md](design/observation-schema-v1.md); a
zero-error corpus validator is the launch gate for every generation run.

**When two candidate actions render identically, collapse them.** ~31% of our
multi-SA cast labels initially looked ambiguous; almost all were
identical-string duplicates (permission routes, same-rendering cost variants).
Collapsing identical (host, description) pairs into one candidate made labels
99.99%+ exact ([ADR-0012](decisions/ADR-0012-d2-d3-closeout.md)). The model
can't distinguish identical descriptors anyway; don't burn label mass on
distinctions without a difference — and don't score "picked a different but
identical 1/1" as an error.

## Training

**High agreement ≠ strength; measure both, trust games.** Our BC agent hit
0.976 held-out agreement and 46.8% winrate vs its teacher; the correlation
between offline metrics and winrate is weak enough that we run winrate arms
(~12 min at our throughput) as the standing eval for every checkpoint, with
offline agreement as the cheap proxy. Exclude forced moves and pass-trivial
windows from agreement or the metric flatters you ("honest agreement").

**Value heads fail quietly; diagnose before scaling.** Three distinct failure
modes, all of which presented as "value BCE stuck": input conditioning (raw
scalars 1,000× larger per-dim than unit-normalized text embeddings — fixed by
scaling, BCE 0.69→0.58); the matchup-entropy floor (21% of our deck pairs go
5–0 — no model beats the prior without reading the board); and the
winner-label poisoning above. A surveyed project found a fourth: pretraining
an encoder on value-only loss teaches it to *discard* the board state
(opponent-life R² < 0 from their own probe — worth stealing as a diagnostic).
Our diagnosis tooling: `anvil/training/diagnose_value.py`, binned by
turns-from-end ([m1-bc-plan.md](design/m1-bc-plan.md), ADR-0013).

## Evaluation

**Do the confidence-interval math before believing any improvement.** 95% CI
on a winrate is ±2.2pp at 2,000 games, ±4.9pp at 400, ±9.8pp at 100. Every
stalled project we surveyed spent weeks chasing 1–3pp "trends" inside
400-game noise. Our standing eval: paired seeds (same decks, same seeds, both
arms), mirrored seats, decisive-game accounting, and a variance-reduction
ledger (AIVAT-style corrections for openers/draws/die rolls) that buys a
further ~5% variance cut and — more importantly — *catches its own modeling
errors* via per-class zero-mean tests
([ADR-0014](decisions/ADR-0014-ante-certification.md)). One of those tests
found that Forge's London mulligan tucks **before** the keep decision, making
re-deal keeps choice-filtered rather than chance — the kind of thing that
silently biases any luck-adjustment scheme.

## Reinforcement learning

**An always-on entropy bonus has no equilibrium under near-zero advantages.**
In mirror self-play with a calibrated critic, policy-gradient terms hover near
zero — so a constant entropy bonus becomes the *only* persistent gradient and
compounds at a rate set by the learning rate until the policy dissolves
(entropy 0.18→4.4 in six iterations at lr 3e-5; the same force was visible as
slow drift at lr 1e-5 one run earlier and looked like "healthy exploration").
Post-mortem and the guardrails we now run — per-iteration KL/entropy/veto
halt triplines, a two-sided critic-vs-reward anomaly rule, entropy *floor*
instead of bonus — in
[ADR-0017](decisions/ADR-0017-run2-entropy-collapse.md). Every warning sign
was in our monitoring one iteration before the collapse; the lesson is to
wire monitors to *halt*, not just to log.

**Record the behavior policy at generation time.** Off-policy corrections
(V-trace ratios, μ-recompute tripwires) need the exact serving-time
distribution; we write per-decision μ records server-side, keyed to the same
sequence the store joins on, and recompute them at training time as a
serve/train skew tripwire ([d6-vtrace-loop.md](design/d6-vtrace-loop.md)).
This caught real bugs (a duplicate-game join chimera, a terminal-bootstrap
double-count in V-trace targets — the latter by unit test before any training
run).

---

## What's reusable directly

- **[Bridge protocol v0](design/bridge-protocol-v0.md)** — six game-agnostic
  answer shapes covering Forge's 109-method decision surface
  ([census](design/callback-census-results.md)); measured overhead 2.6% at 16
  workers. If the community standardizes a "plug your AI into Forge"
  interface, this is our proposal for what the wire should look like.
- **[Observation schema v1](design/observation-schema-v1.md)** — full-state,
  per-entity-visibility records; information set enforced downstream, in one
  place.
- **`forkcheck`** — the fork-fidelity regression harness (static digests,
  twin determinism, full gate under a live model). Run it before trusting any
  state-copying workload on a new engine version.
- **[The upstream worklist](design/upstream-worklist.md)** — what we've sent
  or plan to send to Card-Forge, including the merged #11203 fidelity fixes
  and the queued determinism-hooks PR.
- **The surveys** — [who is building what on Forge and what they hit](design/discord-ai-plotting-survey.md),
  plus deep dives on [a core dev's RL branch](design/survey-dive-austinio-rl-branch.md),
  [manabrew's parity harness](design/survey-dive-manabrew-harness.md), and
  [two adjacent ML projects](design/survey-dive-pricepredictor-magezero.md).

Questions, corrections, collaboration: we're reachable via the Forge Discord
(`#ai-plotting`) and GitHub issues/PRs on this repo.
