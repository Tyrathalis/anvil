# Standing rules — retired

Rules moved verbatim out of [standing-rules.md](standing-rules.md) when they were
superseded or when the mechanism they govern left the recipe. Each keeps its
original text and ADR link; the retirement line names the date and the reason.
Nothing here is wrong — it is history a scoping session no longer needs in front
of it. A retired rule returns to the active file if its mechanism does.

## Retired 2026-09-23 (the M12 documentation pass) — the M10 generative-planner route

The turn-plan schedule, its emission head, the binding `-forceschedule` execution
regime and the serve-side follow counters were the M10 route, closed NEGATIVE at
[ADR-0096](decisions/ADR-0096-m10-closeout.md); none of that machinery is in the
M12 recipe (search as the behavior policy, [ADR-0101](decisions/ADR-0101-architecture-review-m12-recharter.md)).
The general lessons these rules carry survive in the active file's neighbours
(the dense-aux anchor rule of ADR-0085, the fixed-label-batch rules of
ADR-0087/0088, the day-zero-read staging rule of ADR-0094).

- **Conditioning-surface flip gates read the content channel** (its
  true-zero floor); presence floors are banked and SUBTRACTED, never
  absorbed into absolute bars — v1 absolute thresholds do not transfer
  to surfaces whose tokens perturb attention by presence
  ([ADR-0084](decisions/ADR-0084-m10-probe-preflight.md)).
  *Retired 2026-09-23: the M10 planner route's mechanism; not in the M12 recipe.*
- **A conditioning surface's ceiling funds only the execution regime it
  was measured in** — the M10 ceiling (+13.5pp) was measured under
  binding `-forceschedule` execution and six probes tried to earn it on
  an advisory surface ([ADR-0094](decisions/ADR-0094-m10-reset.md)).
  *Retired 2026-09-23: the M10 planner route's mechanism; not in the M12 recipe.*
- **The degeneracy veto's emission axes (pure-hold, length) read
  FIRST-WINDOW emissions only** — revision emissions (opponent-action /
  end-step re-emits, ~80% of emission rows) are legitimately emptier
  late in the turn; the lumped `sched_len_*` counters mis-read probe5
  as drifting to ~28% hold when its first-window hold stayed ≤ 9%
  (ADR-0091 correction; split by the mu `rev` flag until the counters
  split). Full-support emitter labels (certified arm + the natural
  line's witnessed casts) stand as a DESIGN decision — schedule every
  turn — not as a fix for a measured drift
  ([ADR-0092](decisions/ADR-0092-consumer-coupling.md)).
  *Retired 2026-09-23: the M10 planner route's mechanism; not in the M12 recipe.*
- **Serve-side follow and utilization counters inflate on natural-line
  plans and cannot read consumption** — on windows where the fed plan
  is what the policy would do anyway, fed = closed; a consumption read
  must be schedule-conditioned (fed vs mask-closed, and a legal-
  candidate content swap) on label-shaped inputs
  (`scripts/sched_content_probe.py`; probe6 adjudication,
  [ADR-0093](decisions/ADR-0093-m10-probe6-read.md) addendum).
  *Retired 2026-09-23: the M10 planner route's mechanism; not in the M12 recipe.*
- **An autoregressive emission head with a STOP class decodes
  stop-vs-continue (p_stop vs Σ candidates), never whole-row argmax**
  — a calibrated head makes STOP the plurality class at every slot ≥ 1,
  and argmax collapses emitted length to ~1 (probe4: 52% pure-hold /
  mean 1.0 against labels at 8% / 2.45); invisible at init, unmasked by
  the first real supervision
  ([ADR-0090](decisions/ADR-0090-m10-probe4-read.md)).
  *Retired 2026-09-23: the M10 planner route's mechanism; not in the M12 recipe.*
- **Under binding execution the natural line is not an independent
  witness**: a window is labeled only if the certifier rolled it out,
  and the label is the search-adjudicated best of {the policy's own
  plan, the enumerated arms} — never label an unrolled window with the
  policy's own play (the ADR-0085 self-target in a new coat)
  ([ADR-0094](decisions/ADR-0094-m10-reset.md)).
  *Retired 2026-09-23: the M10 planner route's mechanism; not in the M12 recipe.*
- **A binding execution regime is gated by a DAY-ZERO read of the
  planner against the executor it replaces** — binding pays only where
  the planner is at least the executor's equal at the bound windows
  (the distilled planner read −6.7pp as pinned and −4.5pp binding its
  first slot alone; the damage is monotone in the amount bound)
  ([ADR-0095](decisions/ADR-0095-m10-dayzero-read.md)).
  *Retired 2026-09-23: the M10 planner route's mechanism; not in the M12 recipe.*

## Struck (superseded by a later ADR)

- ~~The search values an option under the heuristic's realization; a policy that learns WHICH option cannot execute it by that alone~~ — **struck 09-19 ([ADR-0114](decisions/ADR-0114-m12-route-b-rescoped-void-rescue.md)): on a network arm the copies realize the forced option through the MODEL's CastPlan** (a copy's seats inherit the mainline's bridged tags; 88,395 of 90,955 void copies on `b4-tgtlab` made exactly one forward call — the forced ask); `heuristicRealize` fires only on the unbridged control arm and behind the off `-vetofallback`. The re-warm's harm (over-generalization into casts the AI refuses, scaling with the dose) stands on the fallback read alone ([ADR-0111](decisions/ADR-0111-m12-build4-opening-targets-surface-site.md) addenda).
  *Moved 2026-09-23: struck 09-19 by ADR-0114 (the text above carries the correction).*
