# M10 build spec — the v2 schedule surface as built (graft mechanics of record)

*Status: BUILD IN PROGRESS (opened 2026-08-27, the ADR-0081 inheritance
session). This is the implementation-mechanics record under the
adjudicated structure in [m10-plan.md](m10-plan.md) — every fork there
is user-adjudicated; the pins HERE are implementation details recorded
so the read sessions know exactly what the build did. Anything below
that turns out to be fork-shaped gets surfaced, not buried.*

## Scope (the ADR-0081 inheritance list)

Aux roster E+R; schedule tokens + [PLAN] readout with discrete carry;
revise-on-trigger (4 triggers; trigger-2 = ANY opponent action,
trigger-3 = END STEP; slot cap 6 + mask; failed-slot consumed by
revision — all user-adjudicated 2026-08-27); payment slot-conditions +
PG staged mask; ADR-0075 labels as direct aux (era-scoped);
telemetry-from-birth; day-zero banking. Build-era jar `7c4af49fa4`
(ADR-0025 gate passed 2026-08-27). Graft trunk `d6-run11/iter-019`.
The v1 `--plan` machinery is FROZEN LEGACY (run20 archaeology) — v2 is
a parallel `--sched` flag surface, never a mutation of v1.

## 1. The discrete schedule object

A schedule is an ordered list of ≤6 slots + an implicit hold-set (the
unscheduled remainder). Per slot:

- `e` — the wire entity id (the stable per-game id candidates carry;
  `entity_row_of` maps it to the current window's obs row, −1 when the
  entity has left the visible zones),
- `sa` — the pinned sa_vocab id of the normalized SA string,
- `status` ∈ {PENDING, NEXT, DONE, FAILED} (serve-carry bookkeeping;
  exactly one NEXT among non-terminal slots),
- `afford` — afford-bit at the current window (census-convention
  `resolve_cost` + `can_pay` over `source_views(...).now`, the
  veto-knowability v2 / `v2_target_probe._afford_count` conventions),
- `pay` — payment SUMMARY class (small vocab: amount bucket 0–4+ ×
  colorless-only/colored, + unresolvable, + none ⇒ 12 classes). The
  FULL assignment surfaces at the pay window (actuation pin 1), not
  in the slot token.

Plus a revision index `rev` (0 at emission, +1 per revision, no-op
revisions included).

**Serialization (the discrete carry):** every own-turn mu row gains
`sched: {"slots": [[e, sa_id], ...], "st": "<status chars>", "rev": k,
"emit": 0|1}` — slots listed on every row (they are ≤6 pairs; the
bytes are trivial and full-row self-containedness beats delta
reconstruction). Loader-side reconstruction is a verbatim read —
bit-exact by construction, no pass-0 recompute, no float tripwire
class (the ingestion fork's deciding argument 3).

## 2. Model surgery

- **Sequence layout:** `[STATE], [PLAN], entities, history, sched
  slots (6)` — slots appended at the END (readout indices `out[:,0]`,
  `out[:,1]`, `out[:,2:2+n_ent]` untouched); per-slot padding mask.
- **Slot token** (assembler-owned, the v1 precedent):
  `sched_proj([ent_tok(row) ⊕ sched_sa_emb(sa) ⊕ status_emb ⊕
  pos_emb(k) ⊕ afford ⊕ pay_emb])`, `sched_proj` ZERO-INIT (weight and
  bias). `ent_tok(row)` = the window's already-computed entity token at
  the slot's current row (pointer grounding — attention connects plan
  to board through the shared entity representation); a learned
  `sched_null_ent` vector when `row = −1`.
- **Day-zero identity contract (v2 form — differs from v1, recorded
  loudly):** v1's additive injection rode a token M1 had reserved;
  six NEW positions change attention denominators by presence alone,
  so strict bit-identity with slots fed is unattainable under the
  adjudicated attention-grounded design (pooled injection into [PLAN]
  was explicitly rejected as the compressed-vec path). The v2
  contract, test-pinned:
  1. sched keys absent ⇒ bit-identical to iter-019 (old stores/serve
     paths untouched),
  2. mask all-closed (empty schedule) ⇒ bit-identical (padding-masked
     keys are invisible to other tokens),
  3. slots fed at zero-init ⇒ **schedule-content-invariant bit-exactly**
     (any two schedules produce identical logits — the day-zero
     reliance-vs-content floor is exactly 0),
  4. trained proj + fed ⇒ differs (wire connected).
  The PRESENCE perturbation (fed-vs-empty at zero init) is measured on
  the fixed population at the graft smoke and BANKED as the day-zero
  reliance floor — the KILL clause reads "reliance at day-zero floor",
  which is exactly this number, not an assumed 0.
- **Schedule decode head** (the emission surface): autoregressive
  pointer, the `tgt_query`/`slot_emb` decoder pattern verbatim —
  7 steps (6 + STOP), query `sched_query([state ⊕ prev ⊕ slot_emb_k])`,
  keys = `sched_key(ent_out[cand_rows])` + learned STOP key, masked to
  the window's candidates. Teacher-forced in training; GREEDY at serve
  (deterministic, replayable; the decode is supervised, not PG).
- **E head:** MLP on `out[:,1]` ([PLAN] readout — R1 continuity) → 7
  regression axes (`untapped_total, chained, untapped_{W,U,B,R,G}`,
  the `v2_target_probe._e_axes` definition verbatim).
- **R head:** MLP on the per-step DECODER STATE ⊕ picked-candidate vec
  → 2 axes (`untapped_after`, `afford_after`). *(Corrected from the
  draft's "slot token outputs" during R1: the probe defined R as an
  EMISSION-WINDOW prediction — anticipate the ledger at planning time —
  and slot tokens do not exist at the emission window; the decoder
  state per teacher-forced step is the faithful read point.)*
- **Payment:** no new head — the M9 pay surface (`pay_bias`,
  `pay_kind_emb`, pointer) IS the head; it returns to the graft
  (iter-019 carries no pay params ⇒ fresh at the pinned init, the
  rung-3 values). The plan's slot assignment arrives as a MARKED
  candidate: `cand_paymark` bit on the schedule-consistent goal option.
- **lr groups:** `sched_` heads at 1e-3 (starved-param arithmetic);
  `assemble.sched_proj` at 1e-4 from FIRST launch (the run20 iter-0
  class, pinned in the plan's guard posture); pay params at the M9
  `--pay-lr` group.

## 3. Serve (revise-on-trigger)

- **Carry:** `ModelBackend.sched_carry {(g, seat): SchedState}` —
  `SchedState(turn, slots, statuses, rev, last_sig)`; the v1
  `plan_carry` idioms (lock, FIFO cap, `g < 0` never carries, ckpt
  param gate `carry_sched`).
- **Emission point:** the first own-turn MAIN1 `priority` window with
  obs (the fork-consistent MAIN1 rule — the probe's emission window
  and the sweep's fork window). Pre-MAIN1 windows and off-turn windows
  carry no schedule (mask closed) — off-turn hold-up behavior is the
  hold-set's job, not a second schedule.
- **Status advance:** an own `priority` answer matching the NEXT slot
  (same `e`, same normalized sa) ⇒ DONE at the next own window; slots
  never skip — an answer matching a later PENDING slot is a DEVIATION
  (telemetry), statuses unchanged.
- **Triggers (revision = fresh greedy decode at that window, rev+1;
  no-op = decoded schedule equals the remaining old schedule —
  first-class telemetry either way):**
  1. NEXT slot vetoed/failed — serve-side re-ask signature detector
     (same (t, ph, task) + identical candidate-set signature re-arrives
     after we answered a scheduled slot ⇒ the answer was rejected);
     precision is measured, not assumed (false-trigger rate is the
     no-op telemetry's job),
  2. ANY opponent action resolved during our turn — non-self wire-
     history head changed since the last own window (K=8 rolling
     window; missed-trigger residual is the canonical-register
     watch-set instrument's territory),
  3. entry to the END STEP on own turn (first own window with an
     end-phase `ph`),
  4. schedule exhausted (all slots DONE/FAILED).
  Unprovoked revision structurally disallowed. FAILED slots are
  consumed by the revision (user pin 2026-08-27): the new emission
  replaces the slot list; history lives in the labels rows.
- **mu rows** gain the §1 `sched` field on every own-turn window.

## 4. Loop / loader

- **Reconstruction:** side tensors post-collate (the `rl.py:621`
  pattern): `sched_rows/sa/status/afford/pay/mask` per window from the
  mu `sched` field verbatim; `sched_emit` marks emission/revision rows.
- **Targets** (all trajectory-derived at birth, era-labels join later):
  - decode CE: the turn's realized schedulable casts (in order,
    matched to emission-window candidates by (e, sa); unmatched ⇒
    dropped from the target with a counted `sched_tgt_unmatched`) +
    STOP — the ordered upgrade of v1's action bag; certified best-arm
    seed supervision = a named follow-on rung against the sweep mint,
  - E: `_e_axes` at the turn's last own obs-bearing window
    (`v2_target_probe` conventions verbatim, clamps at birth),
  - R: `untapped_after`/`afford_after` at the post-cast window per
    realized slot (ditto).
- **Aux losses** in pass B: decode CE at emission rows; E smooth-L1 at
  emission rows; R smooth-L1 at filled-slot rows; each with ADR-0057
  auto-calibrated weights (`w_sched`, per-iteration recalibration,
  share telemetry + guards from birth, clips at birth).
- **PG staged mask:** advantage mask at `task == pay_class` rows in
  the PG reduction (`rl.py:1316` — route 1; label-zeroing would poison
  the mu tripwire). Flag `--pay-pg-mask`, ON in the sched recipe from
  birth; the unmask condition is pre-registered at the numerics
  session. The supervised conditional CE (ADR-0075 labels) is the pay
  head's only training signal while masked.
- **The v1 float tripwire does not extend to v2** (discrete carry ⇒
  nothing to drift); the standing mu tripwire keeps covering logp
  parity, including pay windows (unmasked in the tripwire by
  construction under route 1).

## 5. Telemetry from birth (the 5-family roster → monitor keys)

1. consumption — `sched_reliance` (fed vs mask-closed on the fixed
   population; `argmax_flip`, `reliance_l1`; day-zero floor = the
   banked presence perturbation), `sched_share`, `sched_rms`;
2. follow/deviation — `follow_rate` (between triggers), deviation
   classes (`dev_reserved` = off-schedule instant-speed at response
   windows — NEVER counted plan break, the contingent-line fingerprint
   (i); `dev_break`; `dev_realization`), per-trigger revision counts +
   `noop_rev` (false-trigger rate), `missed_rev` residual;
3. ambition — scheduled-vs-realized utilization, emitted-length dist
   (reference 0×11/1×29/2×35/3×70/4×25), `pure_hold_rate` (base
   ~6.5%);
4. validity — per-slot afford-bit calibration vs engine outcomes,
   knowably-invalid emission rate (veto-knowability splitter);
5. payment — `paymark_follow`, ADR-0075 conditional holdout, the
   marginal-attribution read repeatable post-training.

Battery: one `MONITOR_SERIES` tuple per key (the registry contract).

## 6. Rungs (this session's ladder)

- **R1 DONE** (commit `6209549`) model surgery + identity/decode tests.
- **R2 DONE** (`55babb8`) loader/targets + aux losses + PG mask;
  integration smoke w_sched 0.00038 at frac 0.1, tripwire 0; target
  rates ~10 emissions/traj, 2.16 slots/emission, 10.8% unmatched
  (counted). `d6-run18-i000` restored from kopia daily-7 en route.
- **R3 DONE** serve carry end-to-end on the real bridge (4-game smoke
  ×2): trigger-2 gained the opponent-priority-PASS filter (485 false
  fires → 185 in 4 games); zero-init runs row-identical across
  different revision content = content-invariance live; round trip
  ingest → loader → learner with **tripwire 0 violations on a
  live-conditioned store** (the discrete-carry bit-exactness claim,
  proven). Pay tag auto-advertises off `has_pay` (the graft keeps pay
  params) — 286 pay windows/24 games served auto at the +2.0 init,
  each carrying the schedule conditioning.
- **R4 DONE** telemetry + graft + day-zero banking:
  - `graft_sched_init.py` → `data/training/m10-sched-init` (23 sched
    params; pay KEPT at design init = ADR-0073 retirement executed;
    v1 plan params STRIPPED = frozen legacy, `carry_plan` off).
  - Pinned reliance population: `m10-reliance-pop-20260827`
    (24 games, graft-era serve, seed base 20530827 — fresh, NOT
    gate-seeded; replaces the deleted run18 pin for v2).
  - `scripts/sched_reliance.py` per accepted iteration (driver-wired);
    SchedServe counters dump to `<mu>.counts.json` at server stop
    (SIGTERM now = SIGINT path); battery MONITOR_SERIES rows added.
  - **Day-zero BANKED** (`m10-sched-init/reliance-dayzero.json`,
    40 traj / 4,715 conditioned windows): **presence floor
    argmax_flip 0.0125**, `content_flip` 0.0 EXACTLY (the contract's
    case-3 assertion), reliance_l1 0.786 (presence-driven), aux
    baselines decode CE 2.609 / E 0.522 / R 1.800, sched_rms 0.0.
  - **Numerics-session caveat (flagged loudly):** the v1 KILL read
    flip against an absolute 0.005 with a true-zero floor; the v2
    floor is 0.0125 BY PRESENCE, so the kill/FUND thresholds must be
    posed RELATIVE to the banked floor (e.g., flip − floor), never
    absolute — pinned at the probe-launch numerics session.
- **R5 DONE (session 3, 2026-08-27) — the label round:**
  - **Evalset repair RESOLVED as an instrument defect
    ([ADR-0082](../decisions/ADR-0082-payment-evalset-repair.md)):**
    the "unreachable" positives were exact-index scoring on multi-arm
    outcome classes (11/17 wide_choice windows carry ≥2 independently
    certified arms, many margin-identical; `best` tiebreaks by arm
    index). Class scoring adopted end-to-end (`cls` on positives;
    scorer counts `pick ∈ cls`; ingestion trains class-CE); phyrexian's
    13 retired with reason. `payment-evalset-v2` (56 pos / 224 auto /
    13 retired) + `payment-holdout-v1` (the ratesweep set, 19+123 —
    the pre-registered conditional holdout, NEVER ingested).
  - **ADR-0075 label ingestion** (`paylabels.py`): class-CE at the
    post-boundary revalidation observe frames (265/280 joined,
    attrition counted), w_paylab ADR-0057 calibration + share guard —
    the pay head's only signal under the PG mask. The `dataset.py`
    pin-scope note states the reversal loudly (certified ≠ heuristic
    provenance). Day-zero: positive CE 3.85 / auto 0.31. Holdout
    observe frames minted fresh on the build-era jar
    (`run-20260827-holdout-observe`, 142/142, zero misses); day-zero
    holdout banked (0/19 positive, 96.7% auto — the +2.0-bias point);
    `--pay-drill-dir` points there in the probe recipe.
  - **`cand_paymark`** (actuation pin 1): zero-init `pay_mark_emb`
    added into the marked candidate's key; SchedServe computes the
    schedule-consistent goal option (max remaining-slots-affordable
    after the option's taps, most-flexible-spare tie-break, never
    auto), serializes `mark` into the mu sched row (loader parity),
    counts `paymark_follow/deviate`. Honest note: the mark is a
    live-but-untrained feature at birth — the observe-frame label
    windows carry no schedules, so `pay_mark_emb`'s gradient arrives
    post-unmask or from a future schedule-bearing label mint.
  - **Best-arm seed supervision**: `seed_sched_labels.py` minted
    170/170 certified-positive arm schedules (zero drops) →
    `seedlabels.py` decode-CE enrichment batch (rejoin exact by
    emission dec id; era-asset, cert ckpt recorded), w_seedlab at
    frac 0.05 (below the dense term's 0.1 — enrichment, not
    replacement).
  - Integration smoke: all three label terms calibrate together on the
    live-conditioned store, tripwire 0.
- **R6 (2026-08-28) — the COUSINS TOUCH, LANDED
  ([ADR-0083](../decisions/ADR-0083-cousins-touch.md) = the record;
  four sub-pins user-adjudicated on the recorded leans: delve IN
  type-grouped / combat bridged now / costmod applicability-only /
  GOAL_MAX 24):** one fork touch completing the serve contract's
  payment scope before the probe.
  - **Enumeration**: cousin atoms (convoke creature taps — colored
    via own colors or generic, never snow/{C}; improvise artifact
    taps — generic/2-hybrid; delve gy exiles — strictly GENERIC,
    type-grouped classes) as restricted pseudo-atoms in the same DFS:
    main-cost shards only, no floats, kept OUT of `allAtoms` (the
    residual-mana universe the sched scorer reads). `spare(k)` goals
    extend; kinds `spare_graveyard=6`; `chainOrderFeasible` removes
    cousin-paid shards from the main-cost requirement.
  - **Detector rewrite**: convoke/improvise/delve leave; per-spell
    applicability via fork-local `CostAdjustment.staticAppliesTo`
    (ReduceCost + SetCost); assist/offering/emerge stay (spell-gated),
    + TapCreaturesForMana/waterbend conservative; `costmod_late`
    backstop unchanged.
  - **Pool-tie fix**: `spare_pool` goal (kind 7, min pool spend) when
    the window enters with float — the lex-hidden pay-life plan
    surfaces; regression test on the Gitaxian Probe pool-tie board.
  - **Combat costs bridged**: `payCombatCost` override marks the
    nested `payManaCost` window (effect gate relaxed there only;
    costmod skipped — no adjustment on effect costs); same tag,
    auto=0 bit-identical; `combat`/`cmb` kvs; pay-vs-decline stays
    heuristic upstream (ADR-0080's genre untouched).
  - **Directed execution**: `CousinDirective` armed per payer around
    the auto-completion (empty maps = deliberate directive), consumed
    by generated FORCE_OVERRIDES hooks on
    `chooseCardsForConvokeOrImprovise`/`chooseCardsToDelve`; unarmed
    = null = natural. Bridged/sched paths finally-scoped; certify
    arms in `PayDirective.resolve`, swept at next window entry.
  - **Python twin**: `PAY_KINDS` += spare_graveyard/spare_pool;
    `pay_kind_emb` (8, 512) zero-init; graft regenerated; **day-zero
    reliance re-banked IDENTICAL** (argmax_flip 0.012513,
    content_flip 0.0 exact, sched_rms 0).
  - **Proofs**: PaymentEnumeratorTest 16/16 (6 new), Wiring 3/3,
    Certify 4/4, Audit 4/4, Anvil suite 253 green; **ADR-0025 jar
    gate: sched smoke 9,969 census + 72/72 + 72/72 labels rows +
    choice smoke 17,409 census + 84/84 + 84/84 labels rows identical
    modulo ms, sched/choice files byte-identical — ZERO diff classes
    total.**
  - **Obligations forward (probe pre-flight) — RESOLVED 2026-08-28
    ([ADR-0084](../decisions/ADR-0084-m10-probe-preflight.md)):**
    holdout remint ZERO-drift (142/142, day-zero identical); evalset
    remint 263/280 joined, option_mismatch 3→5 = the predicted
    spare_pool/costmod class, floors survive; census (paygoals4,
    verbatim recipe): costmod 25.47%→4.35%, conseq 19.79/g, trunc 0,
    nodecap 0.0068 ✓, forced REBORN as the delve/improvise family
    (129), combat 0/500g natural. Probe recipe repoints `--pay-observe`
    / `--pay-drill-dir` to the 20260828 cousins dirs.

Kill/FUND/unmask + read-protocol numerics PINNED PRE-DATA same session
(ADR-0084; [m10-probe-numerics-draft.md](m10-probe-numerics-draft.md) =
the statement of record). The training probe launches next.

- **R7 (2026-08-29) — EMISSION GROUNDING, LANDED
  ([ADR-0086](../decisions/ADR-0086-emission-grounding.md); executes the
  [ADR-0085](../decisions/ADR-0085-m10-probe1-read.md) surgery after the
  m10-probe1 guard halt):** the two routed items collapse into one move
  — the decode head IS the emitter, so supervised decode on certified
  arms IS supervised emission.
  - **Own-emission dense decode CE RETIRED** (not gated): `sched_term`
    = E/R only; `--sched-frac` 0.1→0.05 (mass-preserving — E+R's share
    of the old bundle). §4's "decode CE: the turn's realized
    schedulable casts" target is DEAD; the loader still mints it
    (counters live) but no loss reads it.
  - **Seed supervision PROMOTED to the primary (only) decode/emission
    signal**: `--seedlab-frac` 0.05→0.1, `--guard-seedlab-share` 0.3,
    `--guard-seedlab-spike` 100× median (the ported ADR-0085 tripline;
    on a fixed certified batch a spike = head divergence). The 170-arm
    mint includes the 11 certified pure holds — hold-vs-emit is in the
    supervision. Empty-emission cost NOT built (fights certified
    holds; ADR-0084 contingency stays pinned).
  - **FUND decode leg restated**: seedlab CE ≤ 0.8× day-zero 2.730022
    (= 2.184; banked `m10-sched-init/seedlab-dayzero.json` via
    `scripts/seedlab_dayzero.py`) — weakly discriminating (probe1 hit
    0.43 while degenerate); emission health rides the degeneracy veto.
    All other ADR-0084 numbers verbatim; no graft change, floors stand.
  - **Telemetry composition change (recorded, not hidden)**:
    `sched_share` now E/R-only; `sched_ce` retired (battery row kept
    for pre-0086 runs); `seedlab_raw`/`seedlab_share` join the battery.
  - Relaunch = `scripts/launch_m10_probe2.sh` (fresh name/seed 20280829
    /port 50075 — no phase reuse, ADR-0076 rule satisfied by
    construction). Suite 255 green.

## Found-in-passing (fixed this session)

- `_rl_summary` omitted `plan_share` from the mean key list ⇒ the
  ADR-0057 plan-share guard read `None` and never fired across run20.
  Fixed + regression-tested (`test_rl_summary_surfaces_plan_share`).
