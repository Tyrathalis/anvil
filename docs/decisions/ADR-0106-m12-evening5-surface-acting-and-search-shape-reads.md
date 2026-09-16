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

## Addendum (2026-09-15) — evening 5 read; C1's first read; the recipe pin

- **A6 read (600 games, e3 ckpt, 24 × 2, the search recipe on both arms)**: mode acting − served
  **−0.69 ± 0.81pp** (n 579, 9 up / 13 down); entity one + set + mode acting − served **−0.69 ±
  0.91** (12 up / 16 down). Exposure: 21.9K searched windows per arm; the answer stage cleared the
  0.10 bar 9 times (modes) and 70 times (entities + modes; 63 arms fired clean, 6 unfired, 0 label
  misses). Neither read can resolve a 70-act mechanism at n 579; both say **nothing broke**. The
  pre-registered "gate retires on searched windows" is moot: a fired arm already replaces `askMode`
  gate included, and the gate decides only unacted windows — the structure the rule wanted.
- **Recipe pin**: surface acting stays ON in the shakedown's recipe arm
  (`-searchactkinds entity_one,entity_set,mode`, bar 0.10, T 0.025): neutral in two reads, free at
  the margin (the second round is paid for labels), and the acted answers carry a behavior logp
  for the loop's PG. The answer bar is a settings-pass axis (0.05 would act ≈ 3× as often), not a
  first-read sweep. Ordering / damage stay imitation-only.
- **C1's first read** (heuristic control, 828 windows): next is the resolved leaf (spread 0.086 vs
  roll SD 0.009, 91% resolved; the acting rule converts by the outcome at bar 0.10, +0.062 ±
  0.025); h2 is ≈ 8× noisier per roll (35% resolved, flips 53% of picks) yet its flips read right by
  the CRN end arm (+0.022 ± 0.008) with ≈ 2× the acting conversion — **optimistic by construction**
  (the h2 copy and the end copy of a roll share their first turns). The de-confounded verdict = the
  end arm under `-searchrollsalt` (fork `e63a0cac20`; running). Until it lands: next stays the
  recipe's leaf; h2 is the shakedown's deep arm, not a winner; no second-ply read.
- **Evening 5 CLOSED on components** (the leaf plumb, the acting rule, the mainline arm, the salt,
  `prio_calibration.py`, the acting smoke + read; fork pin `abec2b2982` → `e63a0cac20` on its
  forkcheck). Build 3 closes with it; next = the rebase (B), then Build 4.

## Addendum (2026-09-15 evening) — C1's verdict under independent outcomes

The salted end arm (`-searchrollsalt 20260915`, fork `e63a0cac20`, the same 1,341 windows joined
identical; 814 read) as the outcome judge:

| leaf | flips vs next | d_outcome on flips (CRN end) | d_outcome on flips (salted end) | acting conv. bar 0.05 | bar 0.10 |
|---|---|---|---|---|---|
| next | — | — | — | +0.033 ± 0.016 (147) | +0.035 ± 0.024 (78) |
| h2 | 425/814 | +0.022 ± 0.008 (87/58) | **+0.010 ± 0.010 (79/67)** | +0.029 ± 0.020 (146) | +0.081 ± 0.030 (74) |
| end (CRN) | 596/814 | in-sample | **−0.006 ± 0.008 (91/103)** | +0.049 ± 0.021 | +0.046 ± 0.021 |

- **About half of h2's flip advantage was the shared rollouts**; what remains is within its noise.
  The CRN end leaf as a picker is noise (four binary rolls): its flips read −0.006 by an
  independent outcome after +0.073 in-sample. **The 09-11 pay-slot result (eot → h2 "the better
  target", t 2.9) was read under the same shared seeds and carries the same caveat** — routed: the
  same salted re-read on the pay slot before the loop's payment head uses the h2 pool as its warm
  start (ADR-0105 addendum 09-11).
- **Verdict (C1)**: **next stays the recipe's leaf** — the resolved leaf (91% of windows, roll SD
  0.009) and its acting rule converts by an independent outcome (+0.033 ± 0.016 at bar 0.05). h2
  is ≈ 8× noisier per roll and its picks are not better in general; its bar-0.10 positives convert
  better (+0.081 vs +0.035, the difference +0.046 ± 0.038 — a hint, not a read) — consistent with a
  leaf whose margin is informative only when large. **The shakedown's deep arm stays provisional**:
  top-3 partial re-expansion at h2 with rolls ≥ 4 (to tame the noise) is the shape to price at equal
  box time; expectations lowered. No second ply is in the running; the two-ply arm stays gated.
- **Standing rule born**: a rollout-vs-leaf comparison under common random numbers is optimistic
  for the deeper leaf by construction; the outcome arm of any horizon calibration runs under an
  independent roll salt (`-searchrollsalt`).

## Addendum (2026-09-15 night) — C3, the partial-expansion slot: the shape, its gate, its price

**The price first (the number the shape rests on).** The calibration arms (09-14/15, heuristic
control, 200 games per seat) put an h2 copy at **≈ 10× a next copy** — 2,877 / 1,672 / 5,235 ms
(mean / p50 / p90) against 304 / 146 / 507 — and the deep smoke on the network arm puts it at
≈ 13× in forward calls (≈ 65 per h2 copy vs ≈ 5). C2's "≈ 1 + B/K × 3 ≈ 2.3×" for the deep arm
assumed 3× per copy (the pay slot's eot → h2 step, where eot is already a turn deep). At top-3 ×
h2 × rolls 4 on every searched window that is 12 h2 copies ≈ 35 s per window ≈ 20 minutes of
copies per game against a 15-minute search clock, ≈ 8–10× the recipe's per-window cost: at equal
box time the deep arm plays ≈ ⅛ the games — a few thousand in three days, which cannot move a
network. **Standing rule born**: a search shape's per-copy price is measured on the calibration
arms before its arm is sized; assumed multipliers do not size arms.

**The shape (user took the recommendations, 09-15):**

1. **A natural-margin band gates the deep round, plus a uniform floor.** The deep round runs
   where the first ply's margin (max V − V(natural), on the lifted values) lies in
   **[`-searchdeeplo`, bar)** — the shallow rule sees something but not enough to act on — and on
   a seeded floor draw at `-searchdeepfloor` elsewhere (fork L's labels need every shape on
   ungated windows, the §3d floor). Not a top-two band: 85% of heuristic windows have their top
   two within 0.10 (56% within 0.02), while the natural margin sits **below 0.01 on 77%** of
   them; the band [0.02, 0.10) covers 11% (the network arm's smoke: 22% incl. the floor).
   Defaults lo 0.02 (≈ two roll σ at next), floor 0.1. This is the shape sequential halving has
   and the shape the allocation head (fork L) learns later — a hand rule standing in for the
   head, with the head's floor.
2. **It runs at decide time**, after the controller's ask, so the natural pick is always in the
   deep set and the deep margin is always defined: `Pending.decide` calls the monitor's
   `DeepRound` between the answer stage and the option stage. The deep set = the top-B
   candidates by lifted first-ply value plus the natural when it ranks outside them (B or B + 1).
   The deep copies play the (option, lifted answer) pair the shallow stage proposed: a candidate
   whose answer stage sampled a non-natural answer carries it as a `SurfaceDirective` on its
   deep copies.
3. **The deep values replace the shallow ones for the set; every other candidate is pruned.**
   The option stage samples from the deep set's softmax at T under `-searchdeepbar` (default the
   acting bar; C1's hint that h2 margins mean something only when large makes it a settings-pass
   axis). Two horizons never share a softmax. `by` reads `deep` / `deep_nat`; a deep round whose
   natural copies were all void falls back to the shallow rule (`deep.by: nat_unvalued`).
4. **The surface round stays at the next leaf** (answers at h2 are ≈ 8× noisier and would
   multiply the cost); the deep round values the pair.
5. **Rolls `-searchdeeprolls` (default 4; C1: h2's roll σ ≈ 8× next's), leaf `-searchdeepleaf`
   (default h2; eot | h<N> | end), CRN-paired across the set** on `rollSeedOf(turn, sw, r)` — the
   first `rolls` share the first ply's determinizations. Requires `-searchact`; search-copy /
   recording only, flag-off byte-identical (the forkcheck is the proof).
6. **The row**: the search row gains `deep: {by: gate | band | floor | single | nat_unvalued,
   shallow_margin, shallow_arg, set, v, copies: [{o, leaf, v, kind, calls, snap, ms, a_i}]}` —
   additive (no reader breaks); with it `margin` is the deep margin and `shallow_margin` keeps the
   first ply's verdict — the flip fact fork L's labels are built from. Header pins `deep`,
   `deepleaf`, `deeprolls`, `deeplo`, `deepfloor`, `deepbar`. The census `chooseSpellAbilityToPlay`
   row's `by` names the class (`deep` where the deep round acted).
7. **The bench cell pair** on the deep tip's jar at 24 × 2, 64 games each — the recipe vs the
   recipe + `-searchdeep 3` — is the slot's first honest price: the deep share of forward calls
   per game from the cells' labels (the per-lever number) and the g/h ratio (one cell per arm is a
   draw, not a read — the 09-14 rule; the ratio is what the equal-box-time split needs).

Routed by name: the "continue the copy through its next leaf" optimization (an h2 copy passes
through the next window; a pass-through peek would give the deep set's next value extra rolls
for free) — not built; the deep bar / band / floor as settings-pass axes on the shakedown's deep
arm; the deep arm's clock (`-searchclock` raised on deep runs; the smoke ran 3,600 s).

**The smoke** (fork `5e333e96930`, 4 self-play games on the recipe + `-searchdeep 3`, clock 3,600): 4/4 won, 399 searched windows, wall 2,648 s (p50 460 s per game vs ≈ 150 s on the recipe smoke; max 1,442 s), 0 copy crashes (the one logged exception = the playable-branch prefs leak at FModel startup). Gate census: gate 172 / single 134 / band 82 / floor 11 → the deep round ran on 93 windows (23%), set size 3.0, 18.8 s p50 / 37 s p90 / 67 s max per round; deep copy kinds leaf 871 / end 253 / void 8; forward calls per game 22,265 deep vs 4,380 first ply + surfaces (deep share 84% → the deep arm ≈ 6× the recipe in forward calls, ≈ 3× in one-worker wall); the deep argmax flips the first ply's on 55/93 rounds yet clears the bar on 9 (the mainline acted on all 9: census `by: deep` 9) — at h2's noise the deep round mostly confirms the natural; elsewhere the shallow rule acted 60/306. The mechanism is clean; the price is the read. **The proof + the price**: the queue `build3-deep-queue` (21:24) — forkcheck `run-20260915-build3-deep` **PASS 22:15 09-15 (499/500, 20260969 the standing crash) → fork pin `5e333e96930`** → the bench pair → `data/runs/build3-deep/read.md`.
