# ADR-0059: Two instrument corrections from the M8 D1 build-out — the forkcheck jar-selection bug (ADR-0055's fidelity section measured the wrong jar) and the labels JSON-escape hole (M7 campaign rows silently dropped)

- **Date:** 2026-08-17
- **Status:** accepted
- **Design-doc anchor:** fork discipline (hard conventions), ADR-0025
  boundary-exemption proof, ADR-0055 fork-fidelity section + annex
  (superseded in part), ADR-0052 blast-radius rule (applied twice)

## Context

M8 D1's labels-only harness extension required the ADR-0025 empirical
boundary-exemption proof (same seeds on both jars → identical forkcheck
traces). Running that proof — and the probe itself — surfaced two
standing instrument defects, both found the same day and both fixed
forward.

## 1. The forkcheck jar-selection bug

`scripts/forkcheck/run_forkcheck.sh` selected its jar with
`ls … | head -1` — **alphabetical**, so the stale
`2.0.14-SNAPSHOT` jar (built 08-11 19:34 from the PRE-rebase fork tree)
shadowed the era's `2.0.15-SNAPSHOT` from the moment the boundary
rebase bumped the version. Every forkcheck after that point ran the old
engine:

- `run-20260811-postrebase` (meta claims engine `46c0c0893e`),
- `run-20260811-postrebase-v2` (meta claims era `d798917ae5`),
- `run-20260812-fixedhash` (meta claims era `d798917ae5`)

**all three executed the identical pre-rebase 2.0.14 jar bytes.** The
meta.txt `engine_commit` lines record the repo HEAD at launch, not what
ran.

**Blast radius (ADR-0052 rule):**

| Verdict | Status |
| --- | --- |
| ADR-0055 "post-rebase fork fidelity 11.6%" | Mislabeled: that is the PRE-rebase engine's rate (on 08-11 conditions). The true era rate is measured below — coincidentally similar (11.2–11.4%), so nothing downstream re-prices. |
| ADR-0055 annex "FIXED_HASH discriminator ⇒ deterministic copy-state divergence" | **Unsupported and now contradicted.** The annex's "three runs, two jars" agreement compared one jar to itself three times. Fresh era-jar replication (below) shows a ~0.5%/500 run-nondeterministic game class — the "fully deterministic, seed-stable" conclusion does not hold on the era engine. The next-boundary copy-state forensics item inherits this correction. |
| ADR-0055 boundary verdict itself (rebase accepted, re-baseline 0.5373) | Untouched — the re-baseline ran the true era jar via the harness (run.json pins sha `b7cbedae`), never through run_forkcheck.sh. |

**Fix forward:** newest-mtime selection + a multiple-jar warning +
`JAR=` override in run_forkcheck.sh; the stale 2.0.14 jar moved to
`data/forkcheck/jar-archive/` (it is the M7-probe-era jar of record —
seqp32/forcebranch run.json pin its sha `3e696519`).

## 2. The true era-d798917ae5 fidelity characterization (first actual measurement) + the M8 D1 exemption proof

Three fresh 500-game FIXED_HASH forkcheck runs, same seed set
(20260703+), decks Abzan Armor/Arcane Maelstrom, in
`data/forkcheck/m8d1-proof/`:

| pair | exact-identical | main-hash mism | status flips | divergence |
| --- | --- | --- | --- | --- |
| era vs era (same clean-era jar bytes, two runs) | 497/500 | 2 | 1 | 56 vs 57 (11.2% / 11.4%) |
| era vs ext (clean era build vs M8 D1 extension) | 497/500 | 2 | 2 | 56 vs 56 (11.2% both) |

- **Era fidelity: ~11.2–11.4% fork-replay divergence** — the era's real
  number (prior 7.0% is old-engine/old-conditions; direct comparability
  is broken by the deck-store and conditions drift anyway).
- **A ~0.5% run-nondeterministic game class exists even under
  FIXED_HASH** (seed 20260744 flipped between two runs of the *same*
  jar, main hash included; seed 20260969 differs in all three runs).
  Signature evidence for the wall-clock/timed-AI class: at seed
  20260853 the ext run's *fork* trace equals the era run's *main* trace
  — the same position takes either of two AI lines. Consequence for
  method: under `-XX:hashCode=3` the identity-hash counter is
  positional, so single-seed reruns are not comparable to in-sequence
  results — adjudication of flips requires full same-sequence
  replication runs (done here).
- **The ADR-0025 exemption proof for the M8 D1 extension PASSES:**
  era-vs-ext agreement is statistically indistinguishable from
  same-jar-twice agreement (497/500 both, identical divergence
  tallies). The extension is behavior-identical on the game path at the
  instrument's full resolution. The final probe jar
  (`50b012c8…`) adds only the AnvilRun.jstr escape fix (§3) on top of
  the proven `a33faf25…` bytes — harness JSON formatting, not loadable
  from any game path; the proof carries.

## 3. The labels JSON-escape hole (jstr)

`AnvilRun.jstr` escaped only `\` and `"`. Modal spell text carries
literal newlines (`"Choose one —\n• …"`), so any labels row embedding
such an SA string split into unparseable fragments. Caught live: the
M8 D1 probe's first launch lost **78 of 114 rows** (a row breaks if ANY
of its K=64 recorded first-spells is modal). Fixed: full control-char
escaping (Census.quote always had this; jstr never did).

**Blast radius:** AnvilRun labels rows only (census/obs/corpus paths
always escaped correctly; results rows carry no rules text).
Rollout/forced-branch labels pre-M7 embedded no SA strings — clean.
**M7's forced-seq campaign labels (run14/15/16, `act_first` keys at
K=16 any-of-row exposure) had the hole with silently-dropped rows** —
`seqlabels.load_rows` skipped bad lines without counting. The stores
were deleted at the M7 stale-data pass, so the rate is unmeasurable;
today's K=64 analog (68%) says it was likely material. Consequences:
run16's L_seq trained on fewer windows per iteration than the designed
P≈100, and w_seq calibration read fewer points. **The M7 verdict
stands** — the term demonstrably trained and moved behavior
(ADR-0058's |l_seq| 0.43→0.68 and the behavioral reads are
store-derived, not labels-count-derived); the correction is that the
dose was smaller than designed, which if anything strengthens
"trainable." Recorded, not re-priced. `seqlabels` now warns loudly on
dropped lines.

## Standing lessons

- **A meta line saying which jar SHOULD run is not provenance; hash the
  artifact that ran.** run.json-style sha pinning (harness) never had
  this bug; the forkcheck script did because it resolved its own jar at
  launch. Any script that resolves an artifact by directory listing
  must pin by mtime/sha and warn on ambiguity.
- **Same-instrument replication is not evidence of determinism unless
  the artifact differs** — the annex's three-run agreement was one jar
  self-agreeing. A determinism claim needs a replication axis that
  could actually vary.
- **JSON emitters get control-char escaping at birth** (the clips-at-
  birth pattern, serialization edition), and every loader that skips
  bad lines counts them loudly.
