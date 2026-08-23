# ADR-0072: M9 D4 control — the veto-collapse prediction is FALSIFIED: §3c neither collapses the veto channel nor buys run stability; and the payment evalset certifies a 2-turn proxy, not winrate

- **Date:** 2026-08-23
- **Status:** accepted
- **Design-doc anchor:** [m9-plan.md](../design/m9-plan.md) D4 (done-when 6's
  mechanism verdict); [ADR-0069](ADR-0069-d4-read-adjudication.md) (which
  recorded the prediction as UNTESTED and specified this control);
  [ADR-0062](ADR-0062-m8-closeout.md) (the prediction under test);
  [ADR-0063](ADR-0063-m9-d1-veto-knowability.md) (the kvr instrument)

## Question

ADR-0062's standing account made a falsifiable prediction: **a §3c mana head
collapses vetoes with no penalty.** ADR-0069 found the D4 probe could not
read it — `d6-run18`'s kvr fell 33% but the run had pinned
`drill_selection: None`, and the ledger splits perfectly by campaign status,
so the decline was equally consistent with the missing campaign. The
prediction was recorded as **UNTESTED, not falsified**, and done-when 6 was
amended to say so in those words.

This is the control ADR-0069 specified: `d6-run18` verbatim plus a drill
campaign, §3c on, nothing else changed.

## The run

`d6-run19`, 2026-08-22/23. 12×480 planned, **GUARD HALT at iteration 10**
(`veto_rate 0.3074 > 1.5× iter-0 (0.2029)`), 10 accepted iterations.
Recipe = `d6-run18` exactly, with the campaign restored.

**The campaign could not be restored literally, and the substitute is
recorded here because it bounds the claim.** run17's
`drill-selection-m8-critic` is not replayable post-boundary: `_drill_phase`
re-simulates each entry from its seed on the *current* jar, and the boundary
moved the engine (forkcheck 10.0%), so pre-boundary curated turns land in
different games. Selection assets are ckpt-era-scoped. Nor could in-era
stock be borrowed — **every post-boundary store on disk is either
gate-seeded (`m9-rebaselinearm` runs at `seed_base 20260710`, which is
`final_read.py`'s default; forking training drills from those positions
would contaminate D5's own strength read) or too small.** Stock was
generated fresh: `cycle_stock.py --games-per-arm 1000 --seed-base 20261201`,
1,999 games, 420 addressable losses (46% of losses) → `critic_select.py` at
the a2 composition → **320 entries, the same size as run17's**, ahead share
0.1875, 42 cross-store duplicates dropped by the M8 dedupe. No ADR-0061
era-transfer audit was run: the control needs the drill-fork CONDITION
restored, not a claim that this ordering curates well.

## Result — the prediction fails on both halves

| run | campaign | §3c | halt | veto slope i0–i7 | t | kvr i0→i7 |
| --- | --- | --- | --- | --- | --- | --- |
| run16 | Y | off | i16 | +0.00355 | +0.95 | — |
| run17 | Y | off | **i11** | +0.00097 | +0.41 | flat, 0.1042 at halt |
| run18 | N | **on** | none (8/8) | **−0.00762** | **−7.55** | 0.0635→0.0425 (**−33%**) |
| **run19** | **Y** | **on** | **i10** | **−0.00008** | **−0.02** | 0.0665→0.0640 (**−3.7%**) |

**No collapse.** kvr 0.0665 [.0633, .0698] → 0.0640 [.0609, .0673] — CIs
overlap heavily, validity bar clean at both points (0.9847 / 0.9862). The
slope is indistinguishable from flat and sits inside the drill-fed band
(run11 +0.0007, run17 +0.0010, run13 −0.0030). **run18's −33% does not
reproduce when the campaign is restored.**

**The taxonomy repeats the inverted signature**, now under the opposite
campaign condition — a §3c-attributable collapse would concentrate in the
mana-affordability categories and spare `timing`:

| category | run19 | run18 |
| --- | --- | --- |
| `knowable:generic_short` | **+6.6%** | −35.4% |
| `knowable:colors_short` | −14.3% | −24.6% |
| `knowable:timing` (§3c cannot touch) | **−61.6%** | −51.6% |

In both runs the category §3c cannot affect falls hardest, and the two it
can affect barely move. There is no §3c-attributable collapse in either.
The knowable *fraction* rose 0.5876 → 0.6113, consistent with ADR-0063's
finding that elevated veto populations are MORE knowable: the campaign
pushes probing into precisely the channel the payment head was built to
eliminate.

**No stability dividend.** run19 halted at iteration 10 against a HIGHER
threshold (0.3044) than run17's (0.2925) — one iteration EARLIER than the
§3c-off run17, which halted at i11 (run16 at i16). Textbook runaway
signature at the halt: `rej` 5.115 → 7.888, entropy 0.1508 → 0.2030,
`kl_mu` 0.0019 → 0.0314 (17×), and reward falling 0.5131 → 0.4900 while the
value head ROSE 0.5063 → 0.5220 — the driver's `shaped reward 0.4111 vs
masked head 0.52415` flag is the §6c veto pricing eating the return.

**Selectivity, again, never left 1.0.** Pooled i0–i9: P(dev | positive)
0.0828 vs P(dev | auto-correct) 0.0696, ratio **1.19, z = +1.13** — the same
undifferentiated channel ADR-0069 measured in run18 (1.14, z = +0.75). The
per-iteration maximum was 1.88 (z = +1.62) at i4 and decayed immediately.
The head moved roughly TWICE as fast as run18's (`kind_rms` 0 → 0.0629 vs
0 → 0.0337, on 836 traj/iteration vs 676) and bought no discrimination —
"moved and didn't help" replicated at double the dose.

**One lead, explicitly not a finding.** Precision-on-deviation was 26/53 =
49% in run19 vs 13/39 = 33% in run18 — the direction a density/credit
effect would show, and the campaign IS the density intervention ADR-0069
floated as the alternative route. z = 1.52. Recorded as a lead; reading an
accuracy-flavoured statistic as capability is exactly the error ADR-0069
charged D4's gate with.

## The finding that outranks the result: the evalset certifies a 2-turn proxy

Checked while answering "what would make payment work" — **`payment_certify.py`
scores arms on a `HORIZON = 2` snapshot with per-shape board/tempo proxies**
(`blocker_pressure` = life preserved + creatures kept; `color_hold` = hand
spent + board added; `wide_choice` = any-axis max |delta|; `phyrexian` =
life vs development). Margin thresholds 2.0/2.0/3.0/2.0 on those scores,
sign-consistency 0.75 over k=8 rolls.

**These are not game outcomes.** The 69 certified positives establish that a
directed payment produces a better board state two turns later. Whether that
converts to winning has never been measured.

So: an executor, an enumerator, a sub-head, an evalset and two training runs
were built and spent against a strength gate **without ever establishing
that the taught behavior is worth more than the gate's ±1.1pp noise floor.**
The winrate value of perfect payment play is the single most important
unmeasured quantity in the §3c program, and it gates every remaining design
decision in it.

## Decision

1. **ADR-0062's veto-collapse prediction is FALSIFIED for this surface**, on
   both halves — no collapse under the condition that produces the runaway,
   and no stability dividend. done-when 6's amendment (ADR-0069: "currently
   neither confirmed nor falsified — UNTESTED") is **resolved to falsified**;
   the M9 closeout records a falsification, which ADR-0062 made explicitly
   first-class.
2. **`d6-run18`'s veto decline is attributed to the absent drill campaign**,
   not to §3c. The drill-free/drill-fed split in the ledger is the
   explanation.
3. **The §3c capability negative replicates at double the head dose.**
   ADR-0069's selectivity verdict is not a one-run artifact.
4. **No promotion, no gate read.** run19 ran no arms and made no strength
   claim; the ckpt of record stays `d6-run11/iter-019` and the M9 gate stays
   0.5279 ± 0.0110.
5. **The payment evalset is re-typed: a 2-turn proxy instrument, not a
   winrate instrument.** Every claim resting on "certified" must say which.
   This does not invalidate the drills — it names what they measure.
6. **Routing — RECOMMENDED, pending the user's call.** ADR-0069 argued §3c's
   one remaining payoff was run stability; this run closes that off, so the
   recommendation is now cleaner: **hold the payment surface as
   infrastructure and take the §3a second act.** But the gating analysis
   comes first and is cheap: **run the 69 certified drills to game end
   instead of the 2-turn horizon** and measure the winrate conversion. Three
   outcomes, each routing differently — (a) advantage survives ⇒ the value is
   realizable today and the problem is purely that the model cannot FIND
   those windows, which is the supervised-conditional-signal attack
   (ADR-0015 machinery, built and parked in M2); (b) advantage evaporates ⇒
   either the downstream policy squanders it (the influence-surface
   hypothesis, localized) or the proxy is not predictive; (c) it was never
   worth much in winrate ⇒ payment is not a strength lever at gate
   resolution, no learning mechanism will show it, and the surface is
   infrastructure permanently.

## Standing rules born here

- **An evalset's certification horizon is part of its type.** A proxy scored
  at horizon k certifies proxy advantage at horizon k and nothing else.
  Record the horizon next to the count everywhere the evalset is cited, and
  never let "certified" stand unqualified in a strength argument.
- **Measure the ceiling before building the learner.** Before committing a
  milestone to teaching a behavior, establish that the behavior is worth
  more than the gate can resolve. §3c ran two training runs against a ±1.1pp
  gate without that number.
- **A control must restore the condition, not the asset.** run17's selection
  was unusable and its curation method was irrelevant; what mattered was
  that behind-position drill forks were present in the mixture. Recording
  which of the two a control needs prevents both over- and under-building it.
- **Check whether candidate curation stock is gate-seeded.** `m9-rebaselinearm`
  looked like free in-era stock and shares `final_read.py`'s default seed
  base; using it would have quietly contaminated D5's own strength read.

## Consequences

- **M9's mechanism question is closed** (falsified). The strength question is
  untouched — no full run has been closed in M9.
- **The §3c program's next step is a measurement, not a run**: the winrate
  conversion read on the 69 certified drills. Cheap (69 drills × K on
  existing machinery) and it gates everything else.
- **Deterrence/veto axis:** ADR-0062 closed the deterrence axis and re-typed
  vetoes as a capability diagnostic on the strength of a prediction that has
  now failed. The re-typing survives (vetoes still diagnose capability); the
  specific claim that an interface fix collapses them does not.
- **Unchanged:** the payment-completion queue, the M9 gate pin, the ckpt of
  record. Still due from ADR-0069: the pin-12 forced-family re-mine, and
  evalset repair (phyrexian/wide_choice positives unreachable as
  constructed).
- **Assets born:** `data/runs/early-doom-m9control` (in-era stock traces),
  `data/runs/drill-selection-m9control` (320-entry in-era selection),
  `data/runs/veto-knowability-run19`, `scripts/launch_d6_run19.sh`, and
  `data/training/m9-control-chain.sh` (stock → selection → launch, detached).
