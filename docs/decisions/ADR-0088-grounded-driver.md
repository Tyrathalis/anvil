# ADR-0088: the grounded driver — fixed-batch calibration mechanics fixed loop-wide; the conditioning driver rebuilt as a trajectory-scale certified mint

- **Date:** 2026-08-30
- **Status:** accepted
- **Design-doc anchor:** executes [ADR-0087](ADR-0087-m10-probe2-read.md)
  decisions 2–3, deepened; the full statement of record is
  [m10-grounded-driver-draft.md](../design/m10-grounded-driver-draft.md)
  (drafted 2026-08-30, all five forks user-adjudicated on the drafted
  leans same day)

## Context

The probe pair jointly specifies the conditioning driver's required
shape: probe1's driver was dense + on-distribution but ungrounded
(degenerate fixed point, ADR-0085 — yet content_flip 0.0138 = 2.8× the
kill bar proves the channel consumes under a dense driver); probe2's was
grounded but a fixed, memorizable, boundary-era batch (KL impulse halt,
content dead at 0.0019, live decode CE pulled to 6.404 — past day zero,
ADR-0087). The missing cell — **grounded AND dense AND
on-distribution** — is the spec. The routed items ("calibration fix,
then mint scale") were necessary but not sufficient: a bigger frozen
boundary-era batch still drifts the head off-distribution, just slower.

## Decision (all five forks adjudicated on the drafted leans)

1. **Fixed-batch application mechanics (fork 1), loop-wide**
   (`anvil/training/labbatch.py` + rl.py): per-step chunk subsampling
   (`--lab-k`: ONE k-window chunk per optimizer step, epoch-shuffled
   without replacement; calibration still measures the full batch) +
   linear warmup ramp (`--lab-warmup`, applied steps, per invocation) +
   a **memorization tripline** (`--guard-lab-memorize` 0.5, default
   armed: halt if a term's FIRST post-calibration telemetry-window raw
   < 0.5× its raw-at-calibration — regression-tested from the real
   probe2 numbers, seedlab 0.42/2.73 and paylab 0.23/0.99 both fire).
   First-10-applied raws dumped to `labs_early.json` (the window the
   telemetry rows start too late to see). **Per-window w recalibration
   REJECTED as primary** — on a memorizable batch it amplifies the
   fitted term (w = frac·pg/raw grows as raw collapses).
2. **Cross-iteration amplification closed with the loop's own carry-w
   convention**: `--seedlab-carry-w` built (the `--paylab-carry-w`
   twin); both carry flags + the iteration-0 raw ride `loop_state`
   (the guard's reference once recalibration stops). The banked
   evidence: probe1's per-iteration recalibration grew `w_seedlab`
   **12×** over three iterations (0.000184 → 0.002209) as raw fell on
   the partially-fitted batch — the amplifier is real, not
   hypothetical. The d6-run15 share-drift caveat (PG mass declines
   under frozen w) stays covered by the share guards.
3. **Paylab audited, mechanics applied uniformly (fork 2)**: the
   step-level curves show the same impulse genre — paylab raw 0.994 →
   0.230 (0.23×) within ~10 applied steps, pos-CE 3.69 → 0.85 — milder
   only because 263 windows bottom out above zero. `--lab-k` /
   `--lab-warmup` / carry-w / the memorize guard cover both terms
   through one code path.
4. **The driver rebuilt as a per-era certified mint (fork 3)**
   (`scripts/sched_mint.py`): certify schedule arms on windows sampled
   from the loop's OWN trajectory stores and mint best-arm decode
   labels at trajectory scale. Certification pins verbatim from the
   sweep (ARM_CAP 16, K_ROLLS 8, THETA 2.0, CONSISTENT 0.75,
   select/score winner's-curse split; `schedule_read.py stage1` and
   `seed_sched_labels.py` reused as-is per store). Mint-specific: per
   store replay parameters from the source `run.json` (pairs/seedbase/
   range/gpp AND the generation flag set — `-reask` on,
   `-paytelemetry` off for the probes; the census sweep's flags would
   break parity), rng pin 20280830, no marginal/auto arms, no h4.
   - **Substrate: the two init-ckpt stores** (`m10-probe1-i000` +
     `m10-probe2-i000`, 480 games, ~4,000 eligible windows at the
     census-matching ~8.5/game). Probe3 iteration 0 IS the init ckpt,
     so these are on-distribution by construction — and one serving
     ckpt covers the whole mint. The i001/i002 stores would each need
     their own generating-ckpt server; not worth it for the probe.
   - **Replay parity is WITNESSED, not argued**: the serving side runs
     the generating ckpt sampled at the generation temperature with
     `--fork-instrument` (sampled mainline reproduces via the
     deterministic `noise_seed(game_seed, dec_s)` draws; wire-only
     forceschedule completions accepted with per-roll announced seeds,
     no mu recorded — the M7 mode). `sched_mint.py parity` compares
     every replayed game's obs decision stream (s, m, t, oi) + winner
     against the source store and FATALs on any divergence.
   - **Sizing by rule**: sample ~3,600 → ~1,000 certified labels at
     the banked 28% yield (600 → 170); at `--lab-k 8` and ~180
     optimizer steps/iteration that is ~1.4 visits per window per
     iteration — inside the adjudicated ≤2-visits rule.
5. **The mint-cost bench resolved from banked artifacts** (no fresh
   bench needed — anchor timelines on artifacts): the ADR-0075/0084
   sweep certified 600 windows in ~7.3 h at 8 lanes ≈ **44 s
   wall/window** (~161 rolls/turn at ~1.8–2.2 s/roll). Therefore:
   **per-era re-mint is the cadence** (~3,600 windows ≈ 24 h at 12
   lanes, nice -19, lane-granular resume); the **online per-iteration
   labeler is NOT priced in** (certifying even a 200-window subsample
   ≈ 2.4 h vs the ~30-min iteration clock) and stays routed by name,
   contingent on fork 5's trigger.
6. **Mass (fork 4)**: the mint term runs at **frac 0.05** — the
   retired dense term's *effective* decode mass (0.1 × its ~53% share
   of the day-zero bundle), the mass that drove probe1's content
   movement. ADR-0086's 0.1 was the doubling that fed the impulse;
   the driver default is corrected to 0.05. E/R stays at
   `--sched-frac` 0.05.
7. **Staleness instrument (fork 5)**: `sched_live_ce` — decode CE on
   live trajectory emission rows, measured `grad=False` in the sched
   aux pass (the retired term's target pipeline repurposed as
   telemetry; the loader kept minting the targets). Pre-registered
   read: **live-gap ratio = sched_live_ce / seedlab_raw > 3× over two
   accepted iterations ⇒ the mint has staled** (day-zero ≈ 1.0;
   probe2's terminal signature was 139×). A read, never a guard —
   within the probe it routes the online labeler; at promotion scale
   it is the re-mint clock. Battery row added.
8. **Multi-store label loading**: `--seed-labels` / `--seed-store`
   accept parallel comma-lists (each labels file joins ONLY its own
   store — probe1-i000 and probe2-i000 game indices collide at g=0,
   so MultiStore is not usable here).
9. **What carries**: ADR-0084 gates verbatim; degeneracy veto owns
   emission health; PG-unmask + scalar competency gate unchanged; no
   graft change ⇒ presence floor 0.012513 / content_flip 0.0 stand.
   The ADR-0086 FUND decode leg re-banks its day-zero on the new mint
   (`seedlab_dayzero.py` on the merged label set at the init ckpt),
   bar ≤ 0.8×, still weakly discriminating. The emission-collapse
   question transfers to probe3 intact — iteration 1's generation is
   the first post-surgery emission test. Relaunch = `m10-probe3`,
   fresh name/seed/port per ADR-0076.

## Consequences

- Suite 259 green (4 new: memorize guard on the real probe2 numbers,
  `sched_live_ce` summary surfacing, ChunkSampler determinism/coverage,
  warmup ramp), ruff clean.
- Standing rule born (→ standing-rules.md): **replaying a
  model-generated store requires the generating run's trajectory-
  perturbing flag set AND its serve config, and parity is witnessed by
  an obs-stream comparison, never argued.**
- The probe-pair triangulation (grounded × dense × on-distribution) is
  recorded in the draft §A as the driver spec of record; presence-only
  movement and small-fixed-batch rules from ADR-0084/0087 continue to
  gate reads.
- Routed by name: the online per-iteration labeler (fork 5 trigger or
  promotion-scale pricing); the mint top-up path if certified yield
  lands < ~750 labels (k drops to 4 before any re-sample).
