# ADR-0016: D5 closeout — combat constructs end-to-end; D6 unblocked

- **Date:** 2026-07-14
- **Status:** accepted
- **Design-doc anchor:** §3/§4 (action heads), §9 (bridge); m2-rl-plan D5

## Context

ADR-0012 made D5 combat constructs a hard prerequisite for D6: without
attack/block heads the RL policy cannot express combat, and its BC arms were
predicted to tie by construction (expressiveness deliverable, not winrate).
The declare callbacks never serialized answers, so labels had to come from an
obs-side join; the corpus-wide measurement (113,591 games) found the derived
candidate basis exact for attacks (0 violations / 2.23M attackers) but left
145 block violations unclassified.

## Decision

**Design (settled 2026-07-13, built 2026-07-13/14):** factorized per-creature
heads (attack yes/no logit + dedup count classes + target pointer; block
pointer over attackers∪none with a learned none key) — the autoregressive
decoder is the documented D6 exploration-coherence upgrade path. Scope =
declare attackers/blockers only (order/riders measured ≈0 in corpus; the
rare surfaces return with the drill era).

**Labels: the combat-bounded obs join.** All 145 block violations classified
as one thing — same-turn multi-combat join overshoot (a no-block combat
inheriting a later combat's map; Najeela-style token turns). Bounding the
join at the next declareAttackers dec drives violations to 0 corpus-wide
(v2 re-measure, all 113,591 games) and also fixes a violation-FREE variant
(extra combats re-attacking with the same creature ids) that only the
loader-vs-measure exact reconciliation surfaced. The loader raises on any
residual violation; the v2 record is the proof it can't fire.

**Checkpoint of record: `data/training/d5-combat/last.pt`** (795K steps =
3 epochs incl. the ~1.8M combat windows, 42.1M params). Finals (600-batch):
combat — attack row 0.954 / window-exact 0.923 / target 0.993 / count
0.94–0.98; block row 0.857–0.866 / window-exact 0.82; valpair ≥ val
everywhere (zero held-out-matchup gap). Policy honest 0.9671 vs d2-sa's
0.9748 (−0.77pp, outside run noise) — a real multi-task cost at
combat_weight=1.0, accepted under the ADR-0012 pre-RL scope rule and priced
by the arms (below). Value BCE 0.4531: first policy checkpoint trained
end-to-end on ADR-0013-corrected winner labels.

**Wire: entity-ref AttackMap/BlockMap** (CastPlan rung-1 idiom; the v0
index-form messages were never implemented — reshaped, old fields reserved).
No engine enumeration in the request; the server derives candidates with the
loader's own `_eligible_rows` (zero train/serve skew by construction; obs
`sick` is haste-aware so the basis reconstructs exactly). Combat tags
auto-advertise only when the checkpoint carries trained combat heads.

**Realizers: engine legality only, requirements repaired engine-authoritatively.**
Archaeology findings that shaped them: (1) the engine RE-ASKS invalid attack
declarations — the realizer self-validates and repairs in tiers
(union-merge `AttackConstraints.getLegalAttackers()` → wholesale, the AI's
own invalid-fallback) so the loop terminates by construction; (2) **blocks
are never validated on the controller path** (`validateBlocks` is
human-input-only) — the realizer forced-adds via `mustBlockAnAttacker` to a
fixed point with a terminal AiBlockController fallback, else games go
silently rules-illegal; (3) attack taxes pre-drop via
`removeUnpayableAttackers` (widened public). Census counts
applied/dropped/forced/fallback per window.

## Results

- **Arms tripwire: TIE, as ADR-0012 predicted.** d5-combat 0.4550 ± 0.0249
  vs the D3 record 0.4625 ± 0.0249 (paired seeds, same valpair pairs);
  400/400 decisive, 0 crashes, 0 draws. The −0.77pp honest dip did not cash
  out as winrate. Record: `data/runs/d5-arms-report.json`.
- **Combat telemetry (400 arm games):** attacks 2,250 windows / 3,919
  assignments / **drop rate 0.18%** / 0 forced / 0 fallback; blocks 504
  windows / 298 assignments / drop 3.7% (superset basis meeting
  menace/flying/protection at realization — engine-legal, counted) /
  0 forced / 0 fallback. The model's combat intent reaches the engine
  essentially unfiltered (contrast M0's 65% cast-veto class).
- **The D6 data loop is closed:** model-game obs ingest cleanly and the
  bounded join extracts combat labels from model games with 0 violations —
  self-play combat training data works unchanged.
- Cast veto_rate read 13.9% this arm vs D3's ~10% — same named leak class
  (serve-time re-ask stays the queued lever), worth a re-read at D6.

## Consequences

- **D6 (first V-trace self-play) is unblocked** — the last expressiveness
  prerequisite is in. The AR combat decoder and multi-block (menace answers)
  are documented upgrade paths, not blockers.
- combat_weight (default 1.0) is the lever if the policy-agreement trade
  ever matters; per the pre-RL scope rule it is not worth a BC sweep.
- The block drop class (3.7%) joins the veto class as serve-time re-ask
  candidates (queued, post-D6).
- Fork carries the executor at `380ec69d71`; `load_compat` is the standing
  D5 checkpoint-boundary shim (task_emb growth + fresh combat heads).
