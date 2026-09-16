# ADR-0108: M12 Build 3 closeout — six decision surfaces served from one option-set decoder, the payment head withheld to the loop, the search's shape priced; the record before the rebase

- **Date:** 2026-09-16
- **Status:** accepted
- **Design-doc anchor:** §3d′ (decision surfaces), §3 (the action head's option-set decoder),
  §6 (search as the behavior policy); [m12-plan.md](../design/m12-plan.md) Build order item 3
  (closed here), the running record 09-07 → 09-15; the record of
  [ADR-0105](ADR-0105-m12-build3-decision-surfaces-and-ability-representation.md) (evenings 1–4,
  32 addenda) and [ADR-0106](ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md)
  (evening 5, the search-shape reads, C3)

## Verdict

Build 3's charter (ADR-0105, user-adjudicated 09-07): **every §3d′ surface answered by the
model under search — one surface per evening, one option-set decoder, no gates, each evening
closing on a 600-game paired read that says "nothing broke".** The build ran nine days (09-07 →
09-15) through five evenings and closes with:

| evening | surface(s) | fork pin | served? | the paired read (on − off vs one withheld reference) |
|---|---|---|---|---|
| 1 (09-07) | entity one + entity set | `1ac2ec8dc0b` | yes | +2.06 ± 1.83 (n 584), 3,227/3,227 answers accepted |
| 2 (09-08) | mode (+ tuck served) | `bc01efe1609` | yes, behind the playability gate | ungated −3.24 ± 1.87 → attributed to the mode head's mode-only choice vs the heuristic's joint mode + target choice (−7.3 ± 3.2 in single-mode games) → gated +1.19 ± 1.86; the whole served set −0.17 ± 1.80 |
| 3 (09-08) | trigger / move-to-zone ordering + combat damage (imitation only) | `41ac60d6b21` | yes | +0.52 ± 1.82 (n 580), 1,585 orderings + 61 kill orders accepted |
| 4 (09-08 → 09-11) | payment (the ADR-0102 rescue class as a search tag) | `15863de0b4a` → `287e8cca45` | **no — withheld** | five served pay heads, five negatives (−0.84 to −1.74, each within one SE of the leaf's own prediction); the probe fix recovered ≈ 2.7pp for every network arm |
| 5 (09-14/15) | mainline surface acting (the (option, answer) pair) | `abec2b2982` → `e63a0cac20` | ON in the recipe (`-searchactkinds entity_one,entity_set,mode`) | modes −0.69 ± 0.81, entities + modes −0.69 ± 0.91 — nearly inert at bar 0.10 (9 / 70 acts in 600 games), nothing broke |

**The served set entering the rebase: entity one, entity set, the gated mode head, mull tuck,
ordering, damage — all from `data/training/m12-build3-e3/last.pt`; the pay tag free to bridge
with its head withheld.** Done-when 4 ("every §3d′ family answered by the model under search,
three answer shapes, enumerators with the natural line, each with its smoke read on file") is
met for six of seven families; the seventh (payment) is answered by the engine's auto-payer with
a trained head on file, its serve routed to the loop by a five-read ladder. No promotion; the
ckpt of record stays `d6-run11/iter-019` at 0.5279 ± 0.0110; the day-zero ckpt stays
`m12-build1-stopstate`; every Build 3 checkpoint is a build artifact that serves surfaces, not a
candidate.

## What the build found (in weight order)

1. **The engine adjudicates a served answer only if the answer is realized with everything the
   heuristic's answer bundles.** The mode head's harm was structural, not statistical: a mode the
   AI would not play got the mandatory chooser's targets at cast. The gate (serve-only) fixed the
   read; mainline surface acting (evening 5) is the principled form — the search copy plays the
   mode with its targets and the leaf reads the pair. Standing rule born here (below).
2. **An untrained head costs strength when served, and a probe that touches the game costs it
   whether or not the head deviates.** The init pay head cost +2.56 ± 1.88 withheld-vs-served;
   the auto-payability probe (RNG draws + reservation-memory writes per bridged window) cost
   ≈ 2.7pp on every M12 network arm since Build 1 (three reads one way; `quietProbe` recovered
   it: autoonly − off +0.34 ± 0.48). ADR-0104's day-zero read corrects to dz − ref ≈ +0.9 ± 2.2.
   Rules already standing (served-tag parity; game-neutral probes; a head served only with a fit
   record).
3. **The one-ply leaf is the resolved leaf; depth is a noisy hint, not a better judge.** C1 on the
   priority slot (1,341 windows joined identical across arms): next's spread 0.086 vs roll SD
   0.009 (91% resolved), its acting rule converts by an independent outcome (+0.033 ± 0.016 at
   bar 0.05); h2 ≈ 8× noisier per roll, its flips +0.010 ± 0.010 by a salted outcome after +0.022
   ± 0.008 under CRN (half was shared rollouts); the end leaf is noise as a picker. The pay slot's
   09-11 "h2 the better target" (t 2.9) carries the CRN caveat and is routed for a salted re-read.
4. **Attribution is ablation arms on one reference; the exposure split is post-treatment.**
   Evening 2's flag was attributed by the ladder (entity-only +1.7 / gated mode +1.2 / tuck −0.3 /
   all −0.2 on one withheld reference); evening 3 showed the exposure split's sign follows the
   conditioning arm (trigger +9.6 keyed on ON / −2.2 keyed on OFF).
5. **The search's shape is priced, not assumed.** An h2 copy is ≈ 10× a next copy in wall and
   ≈ 13× in forward calls; the deep arm as drafted would have played ⅛ the games at equal box
   time. The partial-expansion slot (C3) is gated on the shallow natural margin ∈ [0.02, bar) plus
   a floor: ×4.45 forward calls, ×2.83 box time per game, the deep round on 20% of windows, acting
   on 2.2% (24 × 2 bench pair, 09-15).
6. **The heuristic answers no modes in ≈ half of traced mode windows** (the Confluences fizzle
   1,124/1,136) — the leak every network arm shares; the mode head's target once the loop reaches
   it.
7. **Throughput** (the throughput week, inside the build): the fleet (`--servers N`, N = ceil(workers
   / 12)), the 24 × 2 recipe ≈ 490 g/h at rolls 2 without surfaces and **294 g/h with the full
   recipe** (surf 2 + acting; the 09-15 bench cell — the ADR-0106 sizing estimate of ≈ 350 was
   high), the chunk rule (four rounds per worker), the mana-source memo (the grouping 17.9% →
   5.2% of a worker's CPU), the JFR levers named upstream, PR 11916 queued for the rebase.

## Decisions

1. **Build 3 CLOSES.** The plan's Build order item 3 is done; item 4 (Build 4: stack-entry tokens,
   the `sa_emb` switch to the shared ability table + re-warm, format-as-features) opens after the
   rebase (ADR-0106 B), which lands next.
2. **The served set is pinned as above** through the rebase and Build 4; the post-Build-4 read
   re-issues every number in one era (the day-zero numbers carry the probe cost and the
   served-tag term; nothing before `15863de0b4a` compares to anything after it without the
   ADR-0104 correction).
3. **The recipe arm of the shakedown is pinned**: rate 1, rolls 2, `-searchsurf 2`, bar 0.10, T
   0.025, `-searchactkinds entity_one,entity_set,mode`, the next leaf, 24 × 2; the deep arm =
   the recipe + `-searchdeep 3` (h2, rolls 4, lo 0.02, floor 0.1) sized from ×2.83; the shallow-wide
   arm = rate 1, rolls 1, no surfaces. The band / floor / deep bar and the answer bar are
   settings-pass axes, not first-read sweeps.
4. **The payment head's home is the loop** (Build 4½ PG on outcomes; the h2 pool `b3-surflab4` +
   the deviation gate = the warm start) — the 09-11 decision stands; no further offline pay head
   before it.
5. **Routing by name** (no silent loss; each named at Build 4's scoping or the closeout):
   - the certifier merge (Build 4½ or the closeout; the trigger unchanged);
   - the pay slot's salted re-read of the 09-11 h2 result (before the loop's pay head uses the h2
     pool);
   - a fresh keyed surface pool on the post-rebase jar (the damage dec shape; stable keys) at the
     next label regeneration;
   - search from combat windows (the leaf value reaching damage: mainline surface acting or Build
     4½);
   - targets as a surface + the legal-target count option feature (the mode head's structural
     fix beyond the gate; Build 4's representation pass names it);
   - the move-to-zone head's below-baseline agreement (inert on graveyards; a per-callback serve
     switch if a read ever needs it);
   - the rescue class's own read (needs a pool where admitted casts are chosen — the loop);
   - the allocation head (fork L; after C1's labels, Build 4½ / 5) and the two-ply arm (gated on
     the deep arm's gain per box-hour);
   - the pass-through next peek on deep copies (an optimization, unbuilt);
   - `chooseSingleStaticAbility` / replacement / counter-type / naming surfaces (low priority per
     the ledger; keys already dumped);
   - the transfer read (self-play labels vs play against the heuristic; only if the loop's pay
     head stalls);
   - the documentation review session (Build order 4¾) before the big run.

## Standing rules born in Build 3 → [standing-rules.md](../standing-rules.md)

Already recorded at their addenda: an ability's identity is its canonical engine text keyed by
hash (ADR-0105); the key is a function of static text only (the key-stability fix); served-tag
parity in a paired read; a probe on a bridged window is game-neutral; a head is served only with a
fit record; an exposure split keyed on one arm's own game is post-treatment (attribution = ablation
arms on one reference); certify cannot replay AnvilRun games (rollout reads on search windows are
search-directive leaf modes); a served arm's identity gate runs one worker; a search run's load is
part of its recipe; recipes compare at equal box time; a calibration's outcome arm runs under an
independent roll salt; a shape's per-copy price is measured before its arm is sized. **Born at this
closeout** (the evening-2 candidate, now a rule): **a served surface answer is realized with
everything the heuristic's answer bundles — read the engine's realization path for what the
heuristic decides jointly (a mode's targets at cast) before serving the callback alone; where the
bundle cannot be served, the search copy plays the pair and the leaf judges it.**

## Assets carried / retired

Carried: the fork tips `b0567608938` → `5e333e96930` (ability keys + the `-abilities` dump, the
surface serve wire for seven kinds, the enumerator family incl. the modern-rule damage enumerators,
the sub-row frame, the playability gate, the payment surface kind + the copy-side pay gate + the
rescue class (flag-gated), the probe fix, the leaf family on both slots + `snap` + `-searchclock`,
the mana-source memo, mainline surface acting, the roll salt, the partial-expansion slot);
`data/training/m12-build3-e3/last.pt` (serves six surfaces + tuck), the set-keyed pay heads
`m12-build3-e4s` / `-e4h` / `-e4hg` (not served), the keyed pools `b3-surflab2` / `-3` / `-4`, the
ability side-table cache (5,148 abilities, hash-keyed, the Qwen3 pin), `surface_fit.py` /
`surface_distill.py` / `pay_distill.py` / `pay_fit.py` (+ `--eval`) / `pay_gate`,
`surface_served_census.py`, `surface_exposure_read.py` (with its caveat), `pay_calibration.py` /
`prio_calibration.py`, the fleet (`anvil/bridge/fleet.py`, `--servers`, the GPU yield),
`fleet_bench.py`, the smoke + read pairs per evening, `build3_deep_queue.sh` / `deep_bench_read.py`,
the run launcher (ADR-0107). Retired: the unkeyed evening-1 fit path (the keyed pool supersedes
it); the exposure split as an attribution instrument; the pay-only head; the eot pay target as
"the" target (h2 is better-calibrated, pending the salted re-read); the views lever (dropped 09-14).

## Consequences

- The plan: Build order item 3 closed; the running record continues; the milestone table gains no
  row (M12 is the milestone; its closeout is Build 6's read). The Now block keeps the Build 3
  paragraph until the documentation pass trims it (4¾).
- The rebase is next (ADR-0106 B): a dataset boundary — new forkcheck baseline hashes on the new
  jar, era-scoped Ante maps re-fit, every banked pool cross-era and kept as a warm start, PR 11916 +
  the three-cell g/h read riding along, one heuristic reference read + one `iter-019` read on the
  new jar. The dozen fork tips above are what it carries.
