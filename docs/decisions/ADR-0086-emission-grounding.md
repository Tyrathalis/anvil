# ADR-0086: emission grounding — the own-emission decode term retired, certified seed supervision promoted to primary

- **Date:** 2026-08-29
- **Status:** accepted — **amended by
  [ADR-0087](ADR-0087-m10-probe2-read.md)** on two points: the
  `--seedlab-frac` 0.1 pin (decision 2) drove a KL guard halt at
  probe2 iteration 0 via a fixed-batch calibration impulse, and the
  "170 is enough / no fresh mint" lean (decision 9) is FALSIFIED as a
  probe premise — the per-era re-mint is promoted to a prerequisite.
  The retirement, the promotion in principle, and the restated FUND
  decode leg stand.
- **Design-doc anchor:** m10-build-spec §4 (targets/aux losses); executes the ADR-0085 surgery routing

## Context

ADR-0085 routed two surgery items after the m10-probe1 guard halt:
(1) ground the dense decode targets in certified/minted schedules,
(2) anchor the emission head directly. The design round (user-adjudicated
2026-08-29) resolved that **these are one move viewed from two sides**:
the decode head IS the emitter, so supervising decode on certified
schedules at emission rows *is* supervised emission. No second mechanism
is needed.

## Decision

1. **The own-emission dense decode CE is RETIRED, not gated** (`rl.py`
   sched-aux block). Gating on non-empty realized-cast targets would let
   collapse silently defund the term (targets vanish → opposition
   vanishes), and the ADR-0085 standing rule forbids the term absent a
   comparable-mass grounded anchor. The `sched_term` bundle is now
   **E/R only**.
2. **The certified seed-label term is promoted from enrichment to the
   PRIMARY (only) decode/emission supervision**: `--seedlab-frac`
   0.05 → 0.1 (it takes over the retired term's calibration slot);
   `--guard-seedlab-share` 0.15 → 0.3 (the 3×-target convention).
   The 170-window mint includes the 11 certified pure holds, so the
   supervision teaches *when to hold* as well as what to emit.
3. **`--sched-frac` 0.1 → 0.05, mass-preserving**: E+R's share of the
   old three-part bundle at day zero was (0.522+1.800)/(2.609+0.522+
   1.800) ≈ 0.47, so 0.05 carries E/R gradient mass unchanged through
   the surgery instead of silently doubling it.
4. **The empty-emission cost is NOT built.** The derive-to-zero result
   (ADR-0084) showed the environment prices void arms at ~nothing, so
   any value would be hand-set — and a blanket empty penalty fights the
   genuinely-correct certified holds (~6.5% base pure-hold is real
   behavior). Hold-inclusive supervised emission subsumes the anchor
   role. The penalty contingency stays pinned exactly as ADR-0084 left
   it.
5. **The spike tripline ports to the surviving CE term**:
   `--guard-seedlab-spike` (100× median on `seedlab_raw`; regression-
   tested). Seedlab trains on a fixed certified batch, so a max/median
   blowup there is head divergence, not off-mode target sampling. The
   `--guard-sched-spike` flag is kept but inert post-surgery (`sched_ce`
   no longer emitted) — the named guard class survives for pre-0086
   rows.
6. **The FUND decode leg is restated on the seedlab CE** — the only
   ADR-0084 number whose statistic died with the retired term:
   **seedlab CE ≤ 0.8× day-zero = 2.184**, day-zero **2.730022** banked
   exactly at the init ckpt (`m10-sched-init/seedlab-dayzero.json`,
   minted by `scripts/seedlab_dayzero.py`; cross-validates probe1's
   iteration-0 calibration read 2.7301). **Stated loudly: this leg is
   weakly discriminating** — probe1's seedlab CE reached 0.43 *while
   emissions were degenerate* (the head can learn a fixed certified
   batch while emitting empty live), so the emission-health burden of
   FUND sits on the degeneracy veto (pure-hold ≤ 25% / len ≥ 1.0 /
   util ≥ 25%), which is unchanged. Every other ADR-0084 number carries
   verbatim: content_flip <0.005 / ≥0.02, presence floor-relative,
   E ≤ 0.470 / R ≤ 1.620, PG-unmask conditions, scalar competency gate.
   **No graft change** (zero new parameters) ⇒ the banked presence
   floor 0.012513 and content_flip 0.0 stand; no re-bank.
7. **Telemetry composition change recorded, not hidden**: `sched_share`
   post-0086 measures the E/R bundle only, and the day-zero own-emission
   decode CE 2.609 retires with its term — neither is comparable across
   the surgery line. Battery rows annotated; `seedlab_raw`/
   `seedlab_share` added to the battery roster.
8. **Relaunch as `m10-probe2`** (`scripts/launch_m10_probe2.sh`): fresh
   run name, seed base 20280829, port 50071. The fresh name satisfies
   the ADR-0076 rejected-artifact clearing rule by construction (no
   phase reuse possible); `m10-probe1` is kept frozen as a forensic
   asset with its iteration-2 REJECTED marker.
9. **Mint scale (user-adjudicated): no fresh mint before the relaunch.**
   The probe question — does grounded emission hold non-degenerate and
   does the conditioning channel consume — is answerable on the 170.
   **Per-era re-mint** (the sweep certifier on on-distribution states;
   `m10-probe1` stores are certifiable material) is routed by name as
   the follow-on if the probe FUNDs.

## Consequences

- The probe relaunches on standing gates with one restated leg; the
  serve surface, carry, R5 label stack, and pinned population are
  untouched.
- After surgery, **nothing dense pushes live emissions anywhere** — the
  probe is partly a test of whether the certified anchor + PG alone
  produce non-degenerate emission. The degeneracy veto is the tripline
  for the answer "no".
- No new standing rule: ADR-0085's (dense aux never trains on own
  emissions without a grounded anchor of comparable mass) covers this
  design; this ADR is its execution.
- Suite 255 green (new: seedlab spike-guard regression), ruff clean.
