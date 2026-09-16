# ADR-0109: the pre-launch completeness audit — what the model still defers to the heuristic, what still binds throughput, and what closes before the big run (targets as a surface, the allocation head, the void re-roll skip)

- **Date:** 2026-09-16
- **Status:** accepted (user, 09-16: "include the most valuable of these before the big run, to get
  things as complete as possible")
- **Design-doc anchor:** §3d′ (the coverage ledger, updated in this commit), §3d (concession),
  §6 (search as the behavior policy); [m12-plan.md](../design/m12-plan.md) Build order items 4 /
  4½ (amended here), forks D and L

## Context

Build 3 closed ([ADR-0108](ADR-0108-m12-build3-closeout.md)) with six surfaces served and the
rebase next. Before committing the endgame the user asked two questions: does the model still have
decision surfaces where a human would decide but the model is forced to defer to the heuristic — and
are those only "not caught up yet", or structural; and are we using every throughput lever we know.
The audit read the engine's decision API (≈ 144 `PlayerController` callbacks) against the census
controller's overrides, the 14 bridged tags and the surface hooks, and the recipe bench cell's own
rows (09-15, 4,447 searched windows) for the search's waste.

**Why it matters now.** The loop only sharpens what the model answers. A family the heuristic owns at
launch gets no behavior logp, no policy gradient and no lookahead for the whole four-to-six-week
run, and adding it afterward means a new warm start on a checkpoint that never saw it. The launch is
the last cheap moment to close a deferral; the run cannot be amended once it starts.

## The coverage audit

**Model-decided today**: priority casts with their targets, X, optional costs and card faces (all
inside the candidate set), attackers, blockers, mulligan keep and tuck, optional-trigger yes/no,
the binary and number one-fielders, entity picks (tutor, fetch, discard, sacrifice, destroy, zone
change, spell picks), modes behind the playability gate, trigger ordering, library ordering (scry,
surveil, move-to-zone), combat damage.

**Deferred, by category:**

| category | families | status |
|---|---|---|
| trained, withheld on purpose | payment composition + the cost cousins (convoke, delve, combat costs) | the five-read ladder: the offline label cannot price the decision to deviate → the loop (Build 4½ PG on outcomes; the pool + the gate = the warm start). Not a catch-up case. |
| **not traced, and it matters** | **targets chosen outside a cast**: triggered-ability targets, re-targeting, the generic target choosers (`chooseTargetsFor`, `chooseNewTargetsFor`, `chooseTarget`) | fall straight to the heuristic, no hook. Every targeted ETB / death trigger in Commander. The same mechanism that hurt the mode head. The largest true gap by game impact. |
| enumerated, unserved, cheap | naming (`chooseCardName`; needs the belief head), type / color / counter-type picks, replacement + static ordering | one-pick over a small set; a few per game; occasionally pivotal |
| not traced, low weight | card piles (the Fact or Fiction class), damage-prevention division, play or draw, opening-hand Leylines, the resolution-time confirms, concession (§3d: designed, gated, unbuilt) | after the run |

Two things that look like deferrals and are not: (a) **the search's window coverage** — copies fork
only at the acting seat's quiescent MAIN1 / MAIN2 priority (GameCopier resumes copies faithfully
only at the active player's priority), so instant-speed windows, combat and the opponent's turn are
answered by the network alone with no lookahead: a search-coverage boundary, not a heuristic
fallback (search from combat windows is routed; combat is model-decided and trained by outcomes);
(b) **combat legality is GUI-owned in Forge** (Jetz, 09-15): the engine never validates the model's
attacks and blocks — a hazard on the upstream worklist, not a decision the heuristic takes.

## The throughput audit

**What binds:** Java CPU at 24 workers on 32 cores. The servers sit at 62–79% busy with a mean
batch of 3–5, so the GPU is not the constraint (the deep arm at scale would push a fleet toward
a third server; the ceil(workers / 12) rule stands).

Taken: the fleet, the chunk rule, the mana-source memo (the mask 24.5% → 12.9%), the served-run
deadline, the GPU yield. Queued at the rebase: PR 11916 (≈ −5%). Upstream-scale, routed by name:
the copier's card rebuild, the per-event replacement scan, the view recompute — together roughly
half of worker CPU.

**Unexploited and ours** (the recipe bench cell's rows):

| lever | evidence | size |
|---|---|---|
| **search allocation** (fork D as adjudicated, fork L as generalized) | the search acts on 9.5% of windows (420 / 4,447 by = search) and the natural sits within 0.01 of the best on most; every window pays full price at rate 1 | the largest lever we own: ≈ 1.5–2× the games in the envelope at the M10 head's quality (AUC 0.69) |
| **the void re-roll skip** | 29.6% of first-ply copies void at apply (the forced option absent on the copy — a copy-fidelity artifact, deterministic per candidate, so it repeats on the next roll); 12,834 of 141K first-ply calls plus the full copy cost each | ≈ 15% of first-ply copies at rolls 2 (≈ 7% of copy CPU); exact by construction |
| **the surface round's breadth** | 96,968 of 238K copy forward calls (41%) for labels + acting that fired 70 times in 600 games | a settings-pass axis with a large price; or gate the expansion on the first ply's margin as the deep round is |
| the mask cache | off since its gate failed on a key gap (7 / 120 mask-class); ADR-0102's own condition for the re-read (the engine binds) is now met; the memo already took most of the mask's cost | small residual; re-read when convenient |

## Decision

**Before the big run, in order (≈ a week added to a launch two to three weeks out):**

1. **Targets as a surface** (the Build 4 surface evening). The head is the existing target decoder
   queried with the ability key of the trigger / sub-ability; the enumerator is the engine's legal-
   target set; hooks on `chooseTargetsFor` / `chooseNewTargetsFor` / `chooseTarget` in the census
   controller (the same shape as the entity kinds: traced in obs, forced on copies, served by a
   wire tag `mtg.surface.target`); imitation warm start on the heuristic's answers, the sub-row
   distillation term as for the entity heads; the 600-game paired read. **The mode head rides this
   evening** (below). The legal-target count option feature (routed at evening 2) lands with it.
2. **The allocation head** (fork L's first fit; fork D's adjudicated allocation finally served). Input
   = the state at the priority window; label = the search's own margin ≥ bar (and, where the deep
   round ran, its gain per shape) on every search row — the bench cells and the b3e5 arms already
   hold ≈ 10⁵ windows, policy-conditional and regenerated per cycle; served as an extra output on the
   priority ask's forward pass (no extra calls); the Java rate draw becomes the head's probability
   with the uniform floor kept (`-searchfloor`); read as an equal-box-time arm in the shakedown
   (uniform rate 1 vs allocated), the pre-registered rule the same: the best network-alone gain per
   box-hour, ties to the cheaper.
3. **The void re-roll skip** rides the rebase: a candidate whose roll-0 copy voided is not re-rolled
   (its value is NaN either way); recorded on the row (`kind: skip`). Search-copy only; the forkcheck
   proves it.
4. **The surface round's breadth** is a settings-pass axis of the shakedown (B = 1, a surface rate,
   or the margin gate) — no build before it.

**The mode head under a served target surface (the user's question).** The mode head's harm was
never the mode pick — by the leaf value it beat the heuristic (improvable windows 18% vs 30%) — it
was the heuristic aiming the model's mode at cast (−7.3 ± 3.2 in single-mode games), which the
playability gate papers over by refusing modes the heuristic would not have filled. With targets
served, the mode and its targets are one model choice on the mainline AND on the search copies (a
bridged copy plays the pair the model would actually play, so the distillation labels value the
right thing). So the targets evening's paired read carries **three arms**: today's served set
(gated mode) / + targets (gated mode) / + targets with the gate OFF. **Pre-registered: the ungated
arm within one SE of the gated arm → the playability gate retires; a clear negative → the gate
stays and the mode head's remaining loss is attributed on the ladder** (the joint pick is then the
head's own, and mainline surface acting on the pair is the next lever). The mode head is not
refit for this read; a refit on a pool where copies play model-chosen targets follows the
evening if the gate retires.

**Left until after the run** (routed by name at the closeout): the closed-enumeration picks
(type / color / counter type / replacement + static ordering — one evening when the loop is
running), naming (the belief head's consumer), the card piles / shield division / play-or-draw /
opening-hand class, search from combat windows (copier fidelity, upstream-scale), concession
(§3d, gated on a trusted value head; a compute rebate at self-play scale is the argument to
revisit it at the shakedown's read of game length), the mask-cache gate re-read, the engine-side
combat-legality surface (the upstream worklist).

**The sequence** (amends the plan's Build order): the rebase with the void skip riding it → Build 4
(representation) with the targets surface as its surface evening → the allocation head → the
post-Build-4 read → the shakedown with an allocation arm beside the three shape arms → the launch.

## Consequences

- Standing rule born here → [standing-rules.md](../standing-rules.md) (routing): **surface coverage
  closes before a big run, not after** — a decision family the heuristic still owns at launch gets
  no behavior logp, no policy gradient and no lookahead for the run's whole envelope; the audit
  (the engine's decision API vs the bridged tags + hooks, and the search's own waste on a bench
  cell's rows) is a pre-launch step.
- The design doc's §3d′ ledger is updated in this commit (model-decided today; the families Build 3
  landed; the new family — targets outside a cast — at the top of the excluded list).
- Plan amendments: Build order 4 gains the targets surface evening + the void skip at the rebase;
  4½ gains the allocation arm; forks D / L point here for their first serve.
- Cost: ≈ a week; the big-run launch moves from two to three weeks out to three to four.
