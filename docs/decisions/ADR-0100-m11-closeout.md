# ADR-0100: M11 closeout — the option scorer is NEGATIVE as a mechanism (strength opportunities are measurable but not teachable from sparse labels at any surface); the value head plus one simulator step is the asset; next charter = search as the BEHAVIOR POLICY with depth as the scaling lever

- **Date:** 2026-09-06
- **Status:** accepted (user adjudication 2026-09-06: "we can identify opportunities for strength,
  but we can't teach them to the model, and that should be the next priority")
- **Design-doc anchor:** m11-plan.md (doc of record, closed); anvil-design-v2 §3 (action head),
  §3a (search + distillation), §4 (critic), §6 (Grindstone); ADR-0097 (charter), ADR-0098
  (Build 0), ADR-0099 (Build 1 + routes R1/R2)

## Verdict

M11 chartered ONE mechanism: a single network scoring every presented option as an advantage over
the natural line, trained on per-option spreads from a certifier at any decision tag — search
amortized into the network from labels. **The mechanism is negative.** In two days the charter's
staged reads ran to their pre-registered ends:

| build / route | question | read | band |
|---|---|---|---|
| Build 0 (ADR-0098) | does a critic one step after an option rank the rollout spread? | 0.301 ± 0.022 (800 windows) | HYBRID: rollouts stay the label; lookahead = a deployment-gate candidate |
| Build 1 (ADR-0099) | does a trainable-trunk scorer learn the spread? | 0.158 at N=607 → 0.204 at 2,866; arm length alone 0.148 | KILL by the curve (slope +0.03/doubling) |
| R1 | is the critic's one-ply Δ learnable instead? | 0.16–0.25 at N=502 vs a 0.5 bar | KILL |
| R2 | does the head rank single payment options? | 0.29 overall; positive stratum −0.10 | null where the ceiling lives |

What is disproved is narrow and now well-replicated: **within-window option quality cannot be
regressed from the pre-action representation plus option content at the label scales any
certifier of ours produces** (10³ windows), whether the target is a noisy rollout composite or a
clean critic delta, the trunk frozen or trained, the option a sequence or a single action. It is
not label noise (R1), not a frozen trunk (+0.02), and not one surface (R2). It is sample
complexity for a Q-shaped target, on a representation that summarizes the state but does not carry
action consequences.

What is NOT disproved, and is the asset: **the engine plus a value head reads consequences with no
learning** — one ply ahead at 0.30, at the spread's own horizon at 0.46 — and the policy's own
masked value head is within 0.03 of the full-vis critic at every horizon. The information the
scorer could not learn from the pre-action state sits one exact, cheap simulator step away.

## The diagnosis the user named

Seven milestones have measured strength opportunities well (+13.5pp under an oracle over arms,
+2.96pp payment, +9pp per certified window, each read to a small error) and converted poorly:
every route since M4 that consumed those readings as SPARSE LABELS stalled, and the gate floor
(±1.1pp) cannot see the half-point gains that compound. The signal is weak at three layers —
outcome→decision credit (1 bit per ~150 decisions, luck correction worth ~5%), the value head's
state ranking (0.27–0.48 vs rollout truth), and option quality from the pre-action state (0.20) —
but not absent: it is strong in the simulator. **The next priority is teaching, not measuring:**
put the search where the loop can amortize it, at store scale, as the behavior policy.

## Decisions

1. **M11 CLOSES negative on the mechanism.** Done-when 1 met (Build 0 read), 2 killed (Build 1),
   3–6 not reached. No promotion; ckpt of record stays `d6-run11/iter-019`; baseline 0.5279 ±
   0.0110 stands.
2. **The next charter (m12-plan.md, DRAFT): search as the BEHAVIOR POLICY.** One-ply lookahead
   with the policy's masked value head inside generation, margin-gated over the executor, its
   picks amortized by the existing distillation + PG machinery over millions of store windows; the
   value head sharpened as the second build; **search depth, breadth and leaf rolls are the
   scaling levers, designed in from day one** (a search directive parameterized by plies, not a
   one-ply special case). R3 (ADR-0099) becomes that charter's day-zero read, not M11's last item.
3. **The certifier and the spread labels retire to READ instruments** (ceiling measurement,
   certification, drill selection, per-tag attribution) — the role every read said they are good
   at. The K dial and the void legality pre-filter serve the reads, not training.
4. **Routing by name** (no silent loss): tutor targets, trigger order / combat damage, §3b stops,
   mull tuck — unchanged from ADR-0097, re-ranked at the M12 scoping session; **stack-entry tokens
   (§J-10)** rise in priority as a representation completion the behavior search does not need
   but the amortizing policy does; **payment classes** return as a search TAG (single options are
   the cheapest lookahead) rather than a label surface; **semantic option content** (embedding
   ability text with the pinned LLM instead of a 33K string-id table) is named as M12's third
   build if the first two move strength; **deployment lookahead** is no longer routed — it IS
   M12's mechanism, read as the network-alone vs with-lookahead gap at close.

## Standing rules born here → standing-rules.md

- **Measuring a ceiling is not evidence a route can learn it:** any label route funds its mint
  only after a learnability read at ~10³ windows clears a pre-registered bar ABOVE a trivial
  prior on the same holdout (arm length 0.15; the auto-correct sign prior 0.42).
- **Plan-type (composite) option quality is not regressible from the pre-action state at
  harvest scale** — three head shapes, two targets, both trunk modes (ADR-0096, ADR-0099); a
  future plan-type surface shows a within-window ranking above a length prior before a training
  run funds it.

## Assets carried / retired

Carried: `AnvilNet.score_options` + `opt_` params (inert; the option-token encoding survives for
the amortizing policy), `option_scorer_fit.py` (build / build-pay / fit / report — the
learnability instrument the standing rule now requires), `critic_lookahead_read.py` (the
lookahead lane + streaming read; the one-ply value read it produces is M12 Build 0's baseline
number), the recording jar `f4824f3d6` (`-forceschedule -forkobs`; ADR-0025 proof still owed
before it generates a training store), the Build 0 cells (ADR-0098) as the reference for every
value-head sharpening read, the 3,655-window spread corpus (44 MB). Retired: the certifier-by-tag
build, pivotality-aimed sampling as a training lever, the payment surface as a label surface
(Build 2b), the scorer's spread loss.

## Stale-data pass (kill list — deletion on user sign-off; nothing operational references these)

| dir | size | keep / kill | why |
|---|---|---|---|
| `data/runs/critic-lookahead-cl2/workers` | 3.2 GB | KILL | raw obs-forks + census duplicated by the ingested store |
| `data/runs/critic-lookahead-cl1/workers` | 789 MB | KILL | same |
| `data/trajectories/critic-lookahead-cl2-forks` | 893 MB | KEEP through M12 Build 1 | the Build 0 reference states for value-head sharpening reads |
| `data/trajectories/critic-lookahead-cl1-forks` | 219 MB | KILL | subsumed by cl2 (cl1's windows are a subset re-rolled) |
| `data/training/m11-scorer-b1/best-*.pt` | 552 MB | KILL | instrument ckpts; `windows.pt` (44 MB) + curve.json + read.md KEEP |
| `data/training/m11-scorer-r1-k1`, `-k8` | 1.05 GB | KILL ckpts, keep curve.json/read.md | R1 read of record is in ADR-0099 |
| `data/training/m11-scorer-r2-pay/split*/best-*.pt` | 1.6 GB | KILL ckpts, keep windows.pt + curve/read | R2 read of record is in ADR-0099 |
| `data/runs/critic-lookahead-cl1,cl2` (lanes, logs, read.json) | ~300 MB | KEEP | reads of record |

Kill total ≈ 7.4 GB.
