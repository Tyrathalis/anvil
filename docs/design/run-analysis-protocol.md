# Run-analysis protocol — the standing post-run battery

**Doc status:** living · the standing post-run analysis battery (anvil/evals/battery.py)

**Pinned:** 2026-08-12 (user-approved; grew out of
[visualization-opportunities.md](visualization-opportunities.md)).
**Implementation:** `anvil/evals/battery.py` (battery v1 folded into the
ADR-0049 instruments productionization).

## The two rules that make this safe

1. **Diagnostic, never verdict-generating.** Run verdicts come from
   pre-registered gates and nothing else. Everything the battery emits is
   hypothesis-generating: a battery finding is logged under an explicit
   `## Exploratory` heading and cannot graduate to a believed conclusion or
   a lever without its own pre-registered read. (Across ~15 analyses per
   run, something is always p < 0.05 — the garden of forking paths is the
   failure mode this rule fences.)
2. **Mechanized, never remembered.** The battery is code on the default
   path: the selfplay driver and `final_read.py` invoke it automatically and
   its one-line summary rides the completion notification. A procedure that
   depends on remembering to run it will decay (the pgrep lesson: the hook
   stuck, the memory note didn't). Corollary — **read by default:** every
   run's `analysis.md` leads with an `## ANOMALIES` section, the same lines
   are in the notify text, and the session-pickup habit is "open the
   analysis report of whatever finished," not "check if an analysis exists."

## The battery, per run type

| After a… | Standing analyses (all emitted as `analysis/` beside the run: PNGs + `analysis.md`) |
|---|---|
| **Training run** — per iteration (cheap) | monitor curves so far, one panel per `monitor.jsonl` series (ent / KL / veto / first-veto / casts-per-game, all rows and live rows / rej-penalty mass / reward-vs-v0 / the value head's state-ranking Spearman / GPU-yield seconds / gen_s / train_s, and the payment and schedule series when a run has them); holding read on the iteration's stores (hold-then-cast rate — ADR-0049 #3, the flat-curve that named the bottleneck) |
| **Training run** — at run end | full curves; holding-rate trajectory across iterations; **behavioral delta** final-ckpt vs init-ckpt on shared multi-candidate priority windows (agreement, cast-changed %, cast→pass fraction, KL distribution — ADR-0049 #2, the cast-suppression instrument) |
| **Paired eval / final_read** | paired-Δ with CI + **seed-half consistency check** (the run12 lesson, mechanized: halves disagreeing ≫ CI is flagged); turns distribution; game-status/crash census; per-deck winrate spread; veto/rejected-chain summary |
| **Boundary re-baseline** | eval battery + never-cast/never-seen vs pool census (the sideboard-class check: categories made visible) |
| **Labeling campaign / probe** | learning-curve plot; label distribution health; calibration reliability diagram (rides the existing `critic_calibration.py` / probe harnesses as they next run) |

The battery implements the training-run and eval rows. The boundary and
campaign rows are not built; they land with their next natural run.
Instruments added later join this table in the same commit that adds them.

The battery runs by itself. To re-run a part by hand:

```bash
uv run python -m anvil.evals.battery run-end --run-dir data/training/<name>
```

```bash
uv run python -m anvil.evals.battery eval-read --name <name> --arm-dirs <run dir>,<run dir> --report <report.json> --out-dir <dir>
```

`monitor --run-dir <dir>` redraws the curves alone, `holding <store> ...` is
the holding read on any stores, and `delta --ref <ckpt> --new <ckpt> --stores
<store>` is the behavioral delta between any two checkpoints.

## Conventions

- **Generated-at-artifact-time, never a living service:** every output is a
  side effect of a script that already runs, written to
  `<run-dir>/analysis/` (or next to the report json for reads), stamped with
  ckpt/store/era provenance. No dashboards, no servers.
- **Plots are communication, not evidence.** A plot never becomes the thing
  a verdict cites; the numbers in `analysis.json` are the citable record.
- **Anomaly thresholds are encoded, versioned, and two-sided** where the
  ADR-0017 lesson applies. An anomaly line is a prompt to look, not a
  verdict.
- **Baselines:** behavioral instruments compare against the era's baseline
  read (first one: the d3-rebaseline stores, era `d798917ae5`). A new era
  boundary re-runs the baseline read as part of its re-baseline.
