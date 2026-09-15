# ADR-0106: M12 Build 3 evening 5 — mainline surface acting, the rebase before Build 4, and the search-shape reads (the leaf calibration on the priority slot, the multi-arm shakedown, the allocation head)

- **Date:** 2026-09-14 (session 3, the design session before evening 5's code)
- **Status:** accepted
- **Design-doc anchor:** §3d′ (decision surfaces), §6 (search as the behavior policy); amends
  [m12-plan.md](../design/m12-plan.md) Build order items 4 / 4½ and fork F

## Context

Build 3 is one evening from closing. Served from the e3 checkpoint: entity one, entity set, the
gated mode head, mull tuck, ordering, damage (the ladder on one reference: all served −0.17 ±
1.80 vs withheld — nothing broke). The payment head is withheld and routed to the loop after five
negative serves (ADR-0105 addenda 09-09 → 09-11). The throughput week closed (the fleet, the
24 × 2 recipe ≈ 490 g/h at rolls 2, the chunk rule, the mana-source memo, PR 11916 queued). The
box is idle; the tree is clean at `e928c4b`; the fork checkout sits at pin `1dd36f7342`.

Evening 5 was routed by ADR-0105 (addendum 09-08 midday) as **mainline surface acting on
modes**: the principled replacement for the playability gate. The gate exists because the mode
head's pick is mode-only while the heuristic's is a joint mode + target choice — a mode the AI
would not play gets the mandatory chooser's targets at cast (−7.3 ± 3.2 in single-mode games
pooled over three arms). The search copy plays the mode with its targets, so a badly aimed mode
reads as a lower leaf; the engine + the value head replace the heuristic's judgment.

What exists: the search's second round (`-searchsurf B`, ADR-0103 item 7) expands the FIRST
traced surface callback on the top-B first-ply candidates' paths, one copy per enumerated answer
under a `SurfaceDirective`, and records `sub` rows with a leaf value per answer. What is missing:
nothing on the mainline ever arms a `SurfaceDirective` from those values. Evening 5 is the
acting rule (ADR-0104 item 2) extended from the priority option to the (option, answer) pair.

Three questions beside evening 5 were put by the user in the same session: where the upstream
rebase goes (upstream is 263 commits past the engine pin `23c3d2a85d` of 08-22, tip 09-15); how
long the big run takes; and whether the search's depth-vs-game-count trade-off should be read
before the run — **"signal strength has been an issue for us in the past and search depth is
potentially a strong lever for that"** — with the further aim that the model should be able to
learn for itself which kinds of assessment are useful to it.

## Decision

### A. Evening 5 — mainline surface acting (seven pins)

1. **The choice is made at the priority window, jointly.** Modes are chosen inside the cast
   (`PlaySpellAbility` → `CharmEffect.makeChoices`), before payment; there is no quiescent state
   to fork at the callback. The search values the (cast option, surface answer) pair at the
   priority window — the second round already does — and the acting rule picks the pair; the
   mainline arms a `SurfaceDirective` for the chosen answer, consumed when the action realizes
   its callback (matched by (seat, kind, ordinal) as on search copies). No mid-action fork.
2. **The natural line on a surface is the served behavior**: the gated mode head's answer where
   it serves (the heuristic's where it does not), the same shape as the priority rule (the
   network's own ask is the natural line). The gate keeps deciding unsearched windows; on
   searched windows the engine's outcome replaces the heuristic's play test — the gate is
   obsolete there by construction.
3. **Bar 0.10, T 0.025, rolls 2 on the surface answers** (the shakedown's priority bar; ADR-0105's
   pin of rolls ≥ 2 for modes — leaf σ 0.026/roll vs mode spreads mostly < 0.01). No bar sweep in
   the first read (the post-hoc bar pick ADR-0104 named).
4. **The rule is kind-agnostic, served on modes first.** The acting rule is written once over
   every `sub` kind; the first read serves it on modes; entity one + set acting is a second arm
   only if the mode arm is not negative; ordering and damage stay imitation-only (damage has
   zero sub rows by construction, ADR-0105 evening 3).
5. **Budget accounting**: surface acting adds copies only at acted windows (the second round is
   already paid); rolls 2 doubles them. Expect the per-game multiplier to move from ≈ 1.75× toward
   ≈ 2.5× forward calls on searched games — measured by the smoke, not assumed. Both arms of the
   read run on the 24 × 2 recipe (the load rule).
6. **The read**: the 600-game paired read on the withheld reference; arms = today's served set
   (gated mode) vs served + mode acting. Pre-registered: acting within one SE of the gated arm →
   the gate retires on searched windows; a clear negative → the value head on modes is not yet
   trustworthy, the gate stays until the loop. (The first read is a test of the value head on
   modes — ADR-0105's caveat stands.)
7. **Sequence after evening 5** (user, this session): **the upstream rebase lands between evening
   5 and Build 4** — see B.

### B. The rebase before Build 4 (user decision)

The rebase (a dataset boundary: new forkcheck baseline hashes on the new jar, era-scoped Ante
maps re-fit, every banked pool marked cross-era and kept as a warm start — ADR-0105 item 5
already treats surface labels as policy-conditional and regenerated per era; the value head's
pretrain composites are training data, not a read) lands **after evening 5 closes and before
Build 4 opens**, carrying PR [#11916](https://github.com/Card-Forge/forge/pull/11916) and the
three-cell g/h read (the throughput week's deferred read). Reasons, in weight order: the endgame
(the post-Build-4 read, the shakedown, the big run, its 2,000-game close) then sits in ONE era
against ONE fresh reference read on the new jar (the post-Build-4 read had to be re-issued anyway
— the day-zero numbers carry the probe cost, ADR-0104 addendum 09-09); the shakedown is the
rebase's landmine catcher (every engine change this project shipped surfaced a silent problem in
its first real run); drift only grows (263 commits now; ≈ three months' worth after the run, the
same dozen fork tips to carry). The alternative — after the big run — would promote a checkpoint
whose number is era-stale on the day it is promoted, with nothing behind the rebase until the
next milestone. Cost: one to three days of Java archaeology, one heuristic reference read + one
`iter-019` read on the new jar (≈ a day of box time).

**Big-run sizing as of this ADR** (the envelope four to six weeks, fixed; games inside it scale
with throughput): priority search at rolls 2 ≈ 490 g/h ≈ 11K games/day → 330–500K games; with
surface acting at rolls 2 (multiplier ≈ 2.5×, estimate) ≈ 350 g/h ≈ 8K/day → 235–350K. Upstream
of the run: Build 4 a few sessions, the post-Build-4 read ≈ a day, the shakedown ≈ three days
(now ≈ a week, see C2) → launch two to three weeks out, close six to nine weeks out.

### C. The search-shape reads (user: worth the week; the infrastructure is built for it)

**The premise.** Depth here is the LEAF HORIZON — how far the copy plays under greedy
intermediates before the masked head reads — not tree depth: `next` (the seat's next quiescent
window, a fraction of a turn; the Build 2 pin; 1×), `eot` (≈ one turn; ≈ 1×), `h2` (two to three
turns; ≈ 3× copy cost), `end` (the outcome, no head call; ≈ 12×, winner's-cursed). The one depth
comparison on file (the pay slot, ADR-0105 addendum 09-11): eot → h2 doubled the positives at
t 2.9; end lost it. Three noises scale differently with horizon: the leaf head's error (σ 0.026
per roll; horizon-flat; strongly CORRELATED across candidates at the next leaf, so differences
cancel it — deeper rollouts decorrelate both the real differences and the noise); chance +
hidden information (linear in windows; rolls average it at linear cost; the end leaf's winner's
curse is a max over noisy samples, worse at 64 leaves than at 8); follow-up competence (a good
line the policy cannot follow reads as bad; grows with horizon; rolls cannot fix it — a second
ply can, at K× per ply, and bootstrapping — the copies play the network under training — is the
cheap version that sharpens through the run for free). Fork F's "the scaling curve is read on the
big run's checkpoints at two budgets" measures the SERVING budget on a fixed checkpoint, not the
training signal per box-hour; nothing on file reads the latter, and it is the number that sizes
the run. A fresh model is the wrong subject (its first 100K games are imitation of the heuristic
— the M1 ladder; the big run starts from the day-zero ckpt): the subject is the day-zero
checkpoint and the early signal is the 1.6pp pretrain debt below `ref` and whether network-alone
moves at all (the charter's kill condition, read early).

1. **The leaf calibration on the priority slot (first; hours, no training).** The pay slot's
   leaf family (`-searchpayleaf next|eot|h<N>|end`, fork `287e8cca45`) is plumbed to the priority
   slot (`SearchDirective.leafAfterTurn` exists; an argument plumb, not a design). Three
   heuristic-control arms on one seed set (the 09-11 instrument: heuristic-played copies, no
   head calls on the `end` arm, the sub rows joined per window), read per horizon: (a) the spread
   of leaf values across candidates vs the roll-to-roll σ — signal-to-noise as a curve; (b) rank
   agreement between horizons and how often the deeper leaf FLIPS the one-ply pick; (c) whether
   the outcome agrees with the flip. Output: where the curve peaks on the priority slot, and
   whether a second ply is in the running. The shakedown's arms are set at the measured peak.
   Runs on the box while evening 5's acting code is written.
2. **The shakedown becomes the search-budget read** (amends Build order 4½ and fork F): two or
   three arms at EQUAL BOX TIME (not equal games — the trade is real only that way), the same loop
   settings, the same day-zero start, each closing with the 2,000-game read vs `ref` + the
   network-alone vs with-lookahead gap + the state-ranking Spearman. Arms (provisional, the
   calibration read sets the horizon): **shallow-wide** (rate 1, rolls 1, next leaf, no surface
   expansion — most games/hour); **the recipe** (rolls 2 + surface acting — evening 5's product);
   **deep** (partial expansion: every candidate at the next leaf, the top-B = 3 re-expanded to the
   measured peak horizon at rolls 2 — ≈ 1 + B/K × 3 ≈ 2.3× rather than 3–4× at full breadth).
   **Pre-registered rule: the big run takes the arm with the best network-alone gain per
   box-hour; ties within one SE go to the cheaper arm.** Power caveat, stated now: at 10–15K games
   per arm a 1pp difference sits inside ±1.1pp; "no detectable difference → the cheap arm" is
   itself the decision. One 64-game bench cell per arm at 24 × 2 measures the actual multipliers
   before the equal-box-time split is set. The settings pass (lr / KL / replay under the dense
   mix) runs on the winning arm before the launch. Cost: the shakedown grows from ≈ three days to
   ≈ a week. A two-ply arm (the user's 8 × 4 then fork 8 × 4 shape: 72 copies/window, ≈ 10–12×,
   ≈ 50K games in the envelope — two million searched windows, thin for PG and for the value
   head's own rollout targets) is **gated on the deep arm showing gain per box-hour first**; not
   built in M12 unless it does.
3. **The partial-expansion slot** (fork): after the first ply, a second expansion of the top-B
   candidates to a deeper leaf under CRN — the shape the surface second round already has, with
   the leaf horizon as the expanded axis. Budgeted in forward calls like everything else; the
   `sub`-row schema gains the horizon (`leaf`) per answer as the pay slot's rows already carry.
4. **The allocation head — the model learns which assessment is useful to it** (user's aim; the
   plan's own "learned version" line, 09-09, given its shape). The pivotality head generalizes
   from "search or not" to "which shape": input = the state (+ the first ply's margin where one
   exists); output = a distribution over search shapes {none, one-ply next, partial-deep, …};
   label = the search's own MEASURED gain per shape at that window — the flip-and-outcome facts
   the calibration read (C1) produces, era-scoped and regenerated per cycle; the uniform
   exploration floor stays (the §3d self-sealing hazard: ungated windows keep producing labels
   for every shape). Deployment = the same allocation under a per-device budget. It is a
   time-management model that allocates its own compute, not a value estimate; the engine
   adjudicates every shape's answer as it does today, and the head never chooses actions. Built
   after C1 has produced its first labels; served in the loop (Build 4½ / 5) with the floor, read
   as budget-matched strength vs the uniform-rate arm.

## Consequences

- Standing rule born here → [standing-rules.md](../standing-rules.md) (search, budgets, run
  sizing): **search recipes are compared at equal box time, never equal games, and the read is
  the network-alone gain per box-hour** (the training-signal question; fork F's two-budget read
  on a fixed checkpoint is the serving-budget question and does not answer it).
- Plan amendments (this commit): Build order 4 gains "the rebase lands before it"; 4½ becomes the
  multi-arm search-budget read; fork F amended; new fork **L (search-shape allocation)**; the
  sizing line re-issued; the running record.
- Evening 5's code, in order: (1) the fork — `SearchDirective.Pending.decide` over the `sub`
  rows (the (option, answer) pair), the mainline `SurfaceDirective` arm consumed at the callback,
  the census fields (`by`, `margin`, the answer, `act_void` per kind), the priority-slot leaf
  plumb (`-searchleaf`), the partial-expansion slot; tests; the smoke; forkcheck (the mainline
  path changes only where the directive acts — the flag-off proof); (2) the calibration read on
  the priority slot (C1) on the box while (1) is written; (3) the 600-game paired read (A6);
  (4) the rebase (B), then Build 4.
- Routed by name: the two-ply arm (gated on C2's deep arm); the allocation head's first fit (after
  C1's labels; Build 4½); the certifier merge (unchanged: Build 4½ or the closeout); the
  three-cell g/h read (at the rebase).
