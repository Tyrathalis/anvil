# ADR-0103: M12 Build 1 — the value head inside the shared trunk, cross-fit on banked labels; Build 3 enumerators — every §3d′ surface named in the observation, forced by a directive on search copies, expanded by the search's second round

- **Date:** 2026-09-06 (session 5)
- **Status:** accepted (Build 1 verdict recorded in the addendum)
- **Design-doc anchor:** m12-plan.md Build 1 + Build 3 (enumerators, Java only); anvil-design-v2
  §3d′ (the ledger), §4 (value head), §6 canonical shape items 1, 5, 6; ADR-0101 §3 (the Build 1
  bars), ADR-0102 item 6 (the corrected label count); ADR-0098 (the one-ply cell)

## Context

Build 0 closed with the boundary jar proven (`aac9f808bcf`). Two items remained inside the Build 0
/ Build 1 window: **the value head pass** that produces the day-zero checkpoint for Build 2's
four-arm read, and **the enumerators** for the Build 3 surfaces (Java side only; the heads come
in Build 3 proper).

What the tree held for Build 1 (both agents' maps, 09-06):

- The value head is one MLP on the `[STATE]` read-out inside `AnvilNet`; it has only ever trained
  on terminal outcomes (BCE in BC and V-trace-rooted BCE in PG). The one graduated rank fit —
  `rank-critic-c2v3`, top-4 trunk layers + head, RankNet on the 11.5K-row labelset, 0.483 held
  out — was a CRITIC (its policy heads drifted; never served).
- The banked rollout labels in the iter-019 era (obs sv=2, pool cf2ca6ba) are exactly three
  families: `labelset-c2-v3` (9,600 c2 rows = K=8 winrate at pre-action states, 1,197 frozen
  holdout rows by the ADR-0036 hash), the cl2 completions (800 windows, 47,510 (arm, roll)
  composites, **the full-vis critic's values at both horizons already banked** in
  `lookahead-read.json` — 107,924 values), and the two m9-rebaseline stores (2 × 1,000 iter-019
  games with outcomes). The mint's 3,294 per-arm rows carry no stored post-action state; the
  drill fork points are rows of the labelset already; the 88 `drillmix*-forks` stores are sv=1
  and cannot join.
- The one-ply cell (masked / eot / K=1 vs comp8 = 0.277 ± 0.022) is computed on the same 800 cl2
  windows Build 1 would train on. A single 20% holdout would read at SE ≈ 0.05 against a bar 0.07
  above the reference — not a measurement.

What the tree held for Build 3: every non-priority callback the heuristic answers is wrapped by
the generated `CensusPlayerController`, but the observation record carries only the option
COUNT (never the option names), and the only forcing abstraction (`ChoiceDirective`, M11) is
index-based, regex-family-gated and hard-coded to two kinds. `SearchDirective` forces one
priority option on a copy and cannot see anything the copy decides on the way to the leaf.

## Decision

### Build 1 — `anvil/training/value_pretrain.py`

1. **One network, policy heads kept.** Start from `iter-019`; train the value head + the top-4
   trunk layers (the proven cell) with a **KL anchor** to the frozen teacher on the pointer logits
   of live priority windows (weight 2.0) so the day-zero checkpoint is a POLICY checkpoint (the
   "Build 1 ckpt alone" arm of the day-zero read is meaningful), not a critic tower.
2. **Three loss families, every one rollout-derived or outcome-derived** (the permanent rollout
   anchor of invariant four): `state` = RankNet (|Δwr|-weighted, gate 0.2) + 0.05 BCE on the
   labelset's wr; `leaf` = soft BCE to the banked full-vis value at every cl2 eot/h2 leaf (the
   full-vis targets, dense — 106,144 leaves banked) + RankNet over arms within each (window,
   roll, horizon) group on the paired composite (gate 1.0 dev units, gap-weighted, clipped at 6);
   `outcome` = BCE on won over 48,000 sampled rebaseline windows + the KL anchor.
3. **The one-ply read is CROSS-FIT.** The 800 cl2 windows split into five folds by game hash;
   each fold's model never sees its fold; the fold reads pool to the ADR-0098 cell at its full
   ~650-window precision. The state-ranking read is the frozen holdout, untouched by every fold.
   Early stopping on an inner split (state inner-val Spearman + one-ply on an inner window
   slice), never on a holdout. The day-zero checkpoint is the `--build` fit on every window.
4. **Bars unchanged** (ADR-0101 §3): GO at one-ply ≥ 0.35 and/or state-ranking ≥ 0.50; KILL if
   neither clears 0.32. Reported alongside: the policy drift on held-out windows (KL to the
   teacher, argmax agreement, value BCE/AUC on won).

### Build 3 enumerators — Java, inert without a directive, recording otherwise

5. **`Surfaces`** (one hand-owned class; the generated wrapper stays logic-free): every §3d′
   callback gets (a) a `dec` that NAMES the option list in the observation (`opts` as entity ids /
   SA labels / names, `surf` = the kind) and adds option cards from unwalked zones (library tutor
   targets) to the snapshot — the "choice-state obs emission" capability floor of §3d′; (b) a
   `force` hook — a `SurfaceDirective` armed on a search copy for (seat, kind, ordinal) returns its
   index answer instead of the heuristic's; (c) an `after` hook that TRACES the callback on
   search copies (kind, ordinal, n, min/max, the heuristic's answer as indices) into the copy's
   `SearchDirective`. Seven answer shapes cover the ledger: `entity_one` (tutor / fetch / single
   spell), `entity_set` (choose-N, discard, sacrifice, destroy, hand-size, spell sets), `order`
   (simultaneous triggers, zone-move order, blocker/attacker order), `scry` (scry / surveil
   partition), `mode`, `name` (card-name faces, type choice), `damage` (combat damage vector with
   the defender's share). 20 callbacks wired through the generator's `SURFACES` table; the M11
   `ChoiceDirective` hooks keep precedence on the two tutor callbacks.
6. **Enumerators are index functions**: natural answer first, deduplicated, capped, seeded (CRN
   across copies). Exhaustive when the shape is small (every single, every k-subset, every
   permutation, every partition, every mode combo); otherwise the natural answer's neighbourhood
   (single swaps, adjacent swaps, single flips, size ±1) then seeded samples. Damage: lethal in
   order, remainder on blocker k or the defender with trample (sum-checked at apply).
7. **The search's second round** (`-searchsurf B [-searchsurfcap C]`): after the first ply, the
   FIRST traced surface callback on the top-B candidates' paths is expanded — one copy per
   enumerated answer with the same forced option and a `SurfaceDirective` for the answer; the
   natural answer's value is the first-ply copy's under CRN (no re-run). Row: `sub:[{o, kind, ord,
   label, n, min, max, nat, ans:[{a, v, kind, calls, miss}]}]`. Per-copy misses (`unfired`, `idx`,
   `sum`, `neg`) are counted, never thrown. This is the anytime shape of §6 applied to the
   surfaces as depth: the priority option is the first ply, the surface answers on its path the
   second.
8. **Boundary status:** recording-only on mainlines (named `opts` on non-priority records; the
   forkcheck runs without `-obs`, so the heuristic path is untouched by construction — proven
   empirically anyway, ADR-0025); the directives are inert unless a search copy arms them. Lands
   as an ADR-0025-exempt commit with its 500-game forkcheck against the 08-21 seeds.

## Consequences

- `scripts/build1_run.sh` (five folds → build → read, resumable), `scripts/build3_surface_smoke.sh`
  + `scripts/surface_smoke_read.py`; `scripts/census/generate_census_controller.py` gains the
  `SURFACES` table (regenerate on engine bumps as before); `SurfacesEnumerateTest` in the fork.
- The day-zero checkpoint of record for Build 2 is `data/training/m12-build1/last.pt` if Build 1
  reads GO or in-band; on KILL the charter's Build 1 kill fires (the leaf evaluator cannot be
  sharpened from banked labels) and Build 2 is adjudicated before any search compute.
- Deferred by name: the Python side of the surfaces (answer-shape heads + the loader reading the
  named `opts` on non-priority records + the distillation term from `sub` rows) = Build 3 proper;
  `chooseCardName` with a predicate (open vocabulary — needs a candidate source; the belief head's
  consumer) and `chooseCounterType` / replacement / static ordering (low priority per the
  ledger); the enumerator-rescue payment class (ADR-0102) still rides the Build 3 payment evening.
- Standing rule born here → standing-rules.md: **a read on a training population is cross-fit** —
  when the read's windows are the training windows, fold the population and pool the held-out
  folds; a single holdout at a fraction of the cell's n cannot resolve the pre-registered bar.

## Addendum (2026-09-06, session 5, evening): the surface smoke

`scripts/build3_surface_smoke.sh 8 0.25 2 8` on the first surfaces jar (8 bridged games on
`iter-019`, rate 0.25, top-2 expansion, cap 8; 209 s): **148 searched windows, 630 first-ply
copies, 140 (22%) traced ≥ 1 surface callback on their path, 116 sub-rows expanded, 0 copy
crashes, 1 directive miss** (a mode answer rejected at apply as `idx`). Window ms p50 334 / p90
1,841 (first ply p50 296 at Build 0 — the expansion is cheap at B = 2). Per shape (Δ = max
V(answer) − V(natural) on the unsharpened head, a smoke number):

| kind | sub-rows | answers | mean n | Δ p50 / p90 / max | Δ ≥ 0.02 |
|---|---|---|---|---|---|
| entity_one (tutor / fetch / single target) | 41 | 172 | 8.2 | 0.002 / 0.027 / 0.098 | 4 / 27 |
| mode | 6 | 24 | 3.0 | 0.110 / 0.262 / 0.262 | 4 / 6 |
| scry | 6 | 24 | 2.0 | 0.003 / 0.008 / 0.008 | 0 / 6 |
| order (trigger / zone order) | 47 | 77 | 1.4 | 0.000 / 0.016 / 0.016 | 0 / 9 |
| entity_set | 16 | 18 | 0.5 | — | 0 / 1 |

Census per game (surface callbacks the heuristic answers): `chooseSingleEntityForEffect` 17.6,
`chooseSingleCardForZoneChange` 31.0, `orderSimultaneousSa` 37.5, `orderMoveToZoneList` 12.4,
`chooseModeForAbility` 7.8, `assignCombatDamage` 6.2, `chooseEntitiesForEffect` 5.8,
`choosePermanentsToSacrifice` 5.8, `arrangeForSurveil` 3.0, `arrangeForScry` 1.9.

Two fixes from the read, in the jar that carries the forkcheck: **trivial callbacks (one option,
or nothing to pick) are never traced or matched** — the first jar expanded one-element orderings
and empty entity sets (order mean n 1.4, entity_set 0.5); and the directive's ordinal counter
now applies the same rule and the same "after the forced option" gate as the trace, so an
expansion copy's ordinal names the same callback the first-ply copy traced. **Modal choice is
the shape with visible headroom** on this head (Δ ≥ 0.02 at 4 of 6 sub-rows, max 0.26); tutor
targets show it in the tail (max 0.098). Damage and name surfaces did not fire in 8 games
(combat damage fires only with multiple blockers on the bridged seat).

## Addendum (2026-09-06, session 5, 21:10): the Build 1 read — GO

`scripts/build1_run.sh` (five folds + build, 30 s per epoch, 25 min wall on the 4090):

| read | Build 1 | reference | bar |
|---|---|---|---|
| one-ply masked / eot / K=1 vs comp8, cross-fit, n 647 | **0.390 ± 0.019** | 0.277 ± 0.022 | GO ≥ 0.35 |
| eot / K=8 | 0.424 ± 0.020 | 0.322 | — |
| h2 / K=1 | 0.440 ± 0.019 | 0.303 | — |
| h2 / K=8 (the composite's own horizon) | **0.686 ± 0.016** | 0.439 | — |
| state-ranking, frozen holdout (1,197 rows) | 0.392 | 0.27–0.48 (0.483 standalone critic) | GO ≥ 0.50 |
| policy drift, 9,643 held-out priority windows | KL 0.0024, argmax agree 99.25% | — | reported |
| value AUC on won, held-out games | 0.90 | — | reported |

**Verdict: GO on the one-ply bar** (two SE clear; every fold's own read between 0.33 and 0.43).
State ranking did not clear its bar: 0.39 against the standalone critic's 0.48 — the joint fit
with the policy anchor and the leaf families gives up part of what a critic tower gets from the
state labels alone. Every fold early-stopped at epoch 6–10 on an inner signal dominated by the
one-ply cell on ~75 windows (SE ≈ 0.06); a labeled second pass (`--stop state --patience 8`,
`data/runs/m12-build1-stopstate`) reads whether stopping on the 1,139-row state inner-val alone
buys state ranking without giving back the one-ply cell. Selection rule, declared before the
read: the day-zero checkpoint of record is the variant with the higher state inner-val at its
selected epoch; both variants' holdouts are reported.

**Day-zero checkpoint:** `data/training/m12-build1/last.pt` (iter-019 policy heads intact by
construction, the masked value head sharpened) — the "Build 1 ckpt" arm of the Build 2 four-arm
read. The h2/K=8 cell at 0.69 says the masked head now ranks composites at the composite's own
horizon about as well as one K=1 rollout (0.47) or the label's split-half (0.53) did before.

## Addendum (2026-09-06, session 5, 21:30): the enumerators' ADR-0025 proof — PASS

`data/forkcheck/run-20260906-build3-surfaces` (500 heuristic games, seed 20260703 = the 08-21
seed set, the surfaces jar built from fork `6eb64b6c538`): **498/500 main-trace hashes identical
to `run-20260821-m9boundary`**; fork fidelity 449 clean / 51 = the baseline's 449–450/50–51. The
two misses: 20260969 = the launch-unstable seed named 09-05; 20260739 replayed twice on the same
jar (`repro-20260739-{1,2}`) gives `9e0365815606ddf6` both times = the 08-21 baseline hash — a
launch-instance artifact of the identity-hash residual, exactly the 20260744 pattern of the
Build 0 final proof. **PASS. The research fork pin moves to `6eb64b6c538`** (Build 0 boundary
`aac9f808bcf` + the exempt enumerator commit).
