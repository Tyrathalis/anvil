# ADR-0105: M12 Build 3 — the decision surfaces' Python side (one option-set decoder, three answer shapes, trained and served one surface per evening) and the system's ability representation (the engine's canonical script text, text-hash keyed, one shared table)

- **Date:** 2026-09-07
- **Status:** accepted (pins); numbers land in addenda per evening
- **Design-doc anchor:** m12-plan.md Build 3 + Build 4 (fork I, fork K); anvil-design-v2 §1
  (encoder), §3 (policy head), §3d′ (the decision-surface ledger); ADR-0103 (the Build 3
  enumerators), ADR-0104 (the acting rule), ADR-0101 §3 item 6 (surfaces as search tags)

## Context

Build 2 closed on both reads (ADR-0104 addenda: IN-BAND on the gate arm, *the value head carries
it* on the control arm). The state review for Build 3 found:

- **The Java side is complete and proven** (fork `6eb64b6c538` → pin `b4825285529`): 20 callbacks
  name their option list in the observation (`opts` + `args.surf`), the heuristic's answer is the
  `ret`, seven answer shapes enumerate on search copies, the second round (`-searchsurf B`) writes
  `sub` rows with per-answer leaf values.
- **The Python side is untouched**: the loader's method table stops at the M1 one-fielders; no head
  reads a surface option set; the server bridges nine tags (`mtg.mulligan_tuck` is sent by Java and
  dropped); the trainer has no distillation term for search picks on priority windows or sub rows.
- **Three gaps the plan text did not name**: (1) no wire tag exists for any surface, so a head that is
  trained cannot be served or read; (2) the acting rule covers priority options only — no mainline
  path applies a search-found surface answer; (3) payment classes as a search tag have no enumerator
  (the ADR-0102 rescue class was routed to "the Build 3 payment evening").
- **Free labels**: the six Build 2 arms recorded 12,000 sv=3 games with named surface options and the
  heuristic's answers — ~18.5 non-trivial surface records per game, ~220K imitation labels on disk.
  No `sub`-row pool exists beyond the smoke's 116 (the arms ran surfaces off).
- **The option text problem**: ability-bearing options (modes, triggers, spells) are rendered as the
  engine's 60-character display strings, and those are ~99% outside the pinned M1 SA vocabulary
  (182/185 mode strings, 251/251 trigger strings in a sample) — a head over them cannot tell the
  options apart by text at all.
- **What the system embeds today** (the fork K question, ADR-0101 addendum / m12-plan fork K): the
  card token is the pinned Qwen3 embedding of the ORACLE rendering fused with static features; no
  ability anywhere has a text embedding — priority candidates use a learned 33K-row string table.
  The Forge script lines (`AB$ Mana | Cost$ T | Produced$ G` vs `Produced$ Any`) are a formal
  effect language the cache never sees — exactly the distinction LordOfThePigs retrains embeddings
  on observed play to recover.

## Decision (user-adjudicated 2026-09-07)

### The surfaces

1. **Train and serve together, one surface per evening.** Each evening lands the loader, the
   decoder mode, the wire tag and the server answer as one unit, so the evening's 600-game paired
   read compares network-alone with the head serving against network-alone with the heuristic
   answering (the "nothing broke" read: no new crash class, misses counted, strength within noise).
   Mainline search acting on surfaces (gap 2) is Java and rides the closing Build 3 evening.
2. **One option-set decoder, three decoding modes** — not three heads. The existing target decoder
   (the pointer over entity rows ∪ players ∪ STOP that already picks cast targets and mulligan
   tucks) is extended with an option-set mask, candidate keys for ability-bearing options (the
   priority head's own candidate mechanism), a shape embedding in the query, and the modes: **set**
   stops inside [min, max]; **ordering** runs to exhaustion with picked keys masked; **ranking** is
   one pick. Damage rides ordering over blockers ∪ the defender (players are pointer keys); scry's
   top partition rides set. It initializes from the trained target decoder so priority windows are
   byte-identical at day zero (a test), and `forward()`/`act()` change together.
3. **Option kinds and their keys**: entities (cards, permanents, players) are entity rows — no text;
   abilities and their parts (triggers, modes, spells, statics, replacements) carry the ability key
   (below); closed enumerations (types, counter types, colors) get a tiny fixed vocabulary; names
   rank against the card table (pool faces exactly; off-pool faces through the all-cards cache).
   Payment stays the M9 goal-kind enum over resource entities — the shared ability table improves
   its context only.
4. **Label mix**: an imitation warm start on the heuristic's mainline answers (the clone IS the
   natural line, so serving it costs nothing at day zero — the M9 "no BC from the heuristic" pin
   was payment-scoped and does not extend to surfaces), then the distillation term toward the
   search's leaf-value softmax over enumerated answers on `sub` rows, then PG through the served
   head's behavior logp in the loop (Build 4½). Fit reads are cross-fit (standing rule).
5. **The sub-row pool is generated first** (`scripts/build3_surface_labels.sh`, launched 14:56
   09-07): bridged self-play on the day-zero ckpt from a worktree pinned at `343901c`, jar
   snapshot of `b4825285529`, rate 1 / rolls 1 / `-searchsurf 2 -searchsurfcap 8`, the acting rule
   ON at the pinned shakedown bar 0.10 (labels on the behavior distribution), obs + census + labels,
   1,000 games, worker bridge deadline 20 s (the 8-worker first-window burst under the expansion
   round poisoned every game at the 5 s default; the same seed plays clean single-worker). Labels
   are policy-conditional and regenerate per era; this pool is the bootstrap for the fit read and
   the term's calibration.
6. **Evening order**: entity one + entity set (tutors, discard, sacrifice, scry's partition, the
   mull-tuck serve completion) → mode → ordering with damage → the payment tag (enumerator +
   distillation into the pay head; the ADR-0102 rescue class) → mainline surface acting. **Naming
   is routed by name to the closeout** (0.3 fires per game; the belief head's consumer).

### The ability representation (the system pin; resolves fork K and pre-empts fork I's key)

7. **One ability representation for the whole system**: the pinned LLM embedding of the ability's
   **canonical engine text** — the host card, the trigger line, the keyword, the script parameters of
   the ability and its sub-ability chain, and the full rules-text description — **keyed by text
   hash**, projected through one shared module that mirrors the card encoder. Priority candidates
   (Build 4, with the planned re-warm), surface options (Build 3), stack entries (Build 4), trigger
   and mode strings all read the same table. The card token stays as it is.
   - **Grounding by construction**: the effect is written in the engine's own language; no learned
     target; a script change is a card change that appends under the hash key, never an era shift
     (invariant seven holds — the text is the card definition, not the engine version).
   - **Fork K resolves**: re-segmentation is done (one line per ability, cost and effect parameters
     as fields); the effect-prediction auxiliary loss becomes **the ADR-0049 frozen probe first**
     (parse the script line into an effect class — mana produced, zone moved, damage, counters,
     draw — and ask whether it is linearly decodable from the Oracle-only embedding and from the
     canonical-text embedding; labels from the parser, no games) and a training term only if the
     canonical-text embedding fails it; his effect-grounded vectors side by side stay routed by name
     with his results as the external read; synthetic held-out cards recombine script lines.
   - **The display render never keys anything.** The 60-character `sa` string stays for the M1
     vocab join; identity rides the key.
8. **The fork carries the identity, the Python side embeds it** (one canon function, in Java):
   `AbilityKey` — `canon(sa)` = `H:` host (+ origin), `T:` trigger params, `K:` keyword original,
   `ALT:`/`OPT:` cost variants, `A:` api + sorted script params per chain link (AI-hint and
   description keys dropped), `D:` the full description; `key` = SHA-256 truncated to 16 hex.
   Every ability-bearing option entry and answer (`decPriority`, `peekPriority`, `castPlan`,
   `Surfaces.optJson`) carries `"ak"`; a store session emits each key's text once per game as
   `"abil":[{h, host, kind, txt}]` on the dec record that introduced it; **`AnvilRun -abilities
   <names.txt> <out.jsonl>`** enumerates every pool card's abilities (all faces: spells, activated
   and mana abilities incl. keyword-generated, each trigger's ability, additional abilities and
   mode lists, statics and replacements) through the same function, so the cache is built from the
   engine and the store's side table is the append path for anything play generates. Recording-only
   (ADR-0025-exempt; forkcheck runs without `-obs`); `AbilityKeyTest` (three cases).

## Consequences

- Standing rule born here → standing-rules.md (engine/data hygiene): **an ability's identity in the
  observation is its canonical engine text, keyed by hash; display renders never key anything, and
  every consumer of ability text (candidates, options, stack entries) reads one shared table.**
- Python side (this build): the ability cache builder (`anvil.encoder abilities` from the dump +
  store side tables, text-hash keyed, fp16, the Qwen3 pin), the frozen probe script, the loader's
  surface records → option-set batch fields, the decoder extension, the imitation fit + cross-fit
  read, the surface wire tags + server answers (Java + Python), the sub-row distillation term.
- Routed by name: mainline surface acting (closing evening); the orchestrator scaling the worker
  bridge deadline from the forge args (the `-searchsurf` burst); `mtg.mulligan_tuck` serve (the
  entity-set evening); `chooseSingleStaticAbility` / replacement / counter-type surfaces (low
  priority per the ledger, keys already dumped); naming (closeout); the Build 4 `sa_emb` switch to
  the shared table + re-warm (unchanged).
- Read instrument per evening: the surface smoke (`build3_surface_smoke.sh` + reader) on the
  sharpened head with the head serving, and `final_read.py` at 2 × 300 games paired vs the
  heuristic, arms = day-zero ckpt with / without the head serving the evening's tags.

## Addendum (2026-09-07, 17:05): the fork commits PROVEN — forkcheck `run-20260907-build3-abilkeys`

Jar `a0ed9e314b5` (ability keys `b0567608938` + the serve wire) vs the 08-21 seeds: **497/500
main-trace hashes identical** (fork fidelity 447/52/1 vs the baseline's 450/50). The three misses:
20260739 and 20260969 = the standing launch-unstable pair (20260739 gave a third hash on replay);
**20260853 replayed to the baseline hash `6ec06cb75d96f2b2` on the same jar** (replay a), the
candidate hash on replay b, and under the fixed-identity-hash diagnostic once each way on the new
jar (the old jar: baseline twice) — launch-unstable, the identity-hash residual class. **PASS at the
ADR-0025 standard → the research fork pin moves to `a0ed9e314b5`.** The evening's served-head
smoke and paired read run on it; the next label run (the first keyed pool) too.

## Addendum (2026-09-07, evening 1 fit): the imitation cross-fit, entity one + entity set

Fold 0 adapter-only (shared decoder frozen): surf_one 0.257 / surf_set exact 0.355 — the frozen
query has no room → `surf_query`/`surf_key` as role copies of the cast decoder's maps (item 2
amended: the mechanism is one decoder; the query / key projections are per role, initialized
equal, so priority windows stay byte-identical while the surfaces train freely). Folds with the
copies (trunk frozen, 3,500 steps / 2 epochs each): surf_one ≈ 0.31 (tutor/fetch 0.28 at 12.4
options; first-option rate 0.20), surf_set exact ≈ 0.47 (discard-from-hand 0.68, sacrifice 0.80).
The ability-option callbacks sit at chance in these stores (no `ak` before `b0567608938`). The
pooled read and the build checkpoint: the chain's `read.md` / `data/training/m12-build3-e1/`.
**The pooled cross-fit read (5 folds, `data/runs/build3-e1/read.md`)**: surf_one **0.308** (n 104,737;
first-option rate 0.202; tutor/fetch `chooseSingleCardForZoneChange` 0.272 at 12.6 options,
`chooseSingleEntityForEffect` 0.397), surf_set exact **0.465** (n 33,888; discard-from-hand 0.650,
sacrifice 0.736, discard-to-hand-size 0.553, `chooseEntitiesForEffect` 0.204, `chooseCardsForEffect`
0.331); the ability-option callbacks at chance (0.110 / 0.059 — no keys in these stores). **Build
checkpoint `data/training/m12-build3-e1/last.pt`** (4,000 steps on every game, trunk + shared decoder
frozen; serves `mtg.surface.entity_one/entity_set`).

## Addendum (2026-09-07, 18:10): the served-surface trace fix PROVEN — fork pin `1ac2ec8dc0b`

The first served-head smoke found that a surface the model serves is never traced on search copies
(the bridged hook returns before the wrapper's after-hook), so the expansion round stopped
enumerating exactly the shapes being taught; `1ac2ec8dc0b` traces the served answer as the natural
line (recording-only on copies). Second smoke: entity_one 24 / entity_set 24 sub rows (0 before),
Δ ≥ 0.02 on 10/24 entity_one rows — the search sees headroom over the clone, which is the
distillation signal. Forkcheck `run-20260907-build3-trace`: **498/500**, the standing pair,
20260739 replays to the baseline hash `9e0365815606ddf6` on the same jar (second replay) — **PASS →
the research fork pin moves to `1ac2ec8dc0b`**. Rule for every served surface from here: the
served answer is the natural line of the expansion round.

## Addendum (2026-09-07, 18:20): evening 1 CLOSED — the paired read (`data/runs/build3-surface-read-b3e1/`)

The fitted ckpt `m12-build3-e1` on the `a0ed9e314b5` snapshot, 2 × 300 games per arm vs the heuristic
on the final_read pairs, network alone: **surfaces withheld 0.513 ± 0.021 (587 games) / surfaces
served 0.530 ± 0.021 (592 games); on − off = +2.06pp ± 1.83 (t 1.1, n 584 pairs, 63 up / 51 down)**.
Served arm: 3,227 bridged surface answers, 3,227 accepted (tutor/fetch 2,101, card sets 661, entity
sets 204, single entities 189, spell-one 72). Crash class identical in both arms (5 BridgePoisoned
each, the standing serving class). **Nothing broke** — the evening's pre-registered read; the diff is
one small-N observation (standing rule), banked, not a strength claim. Entity one + entity set are
served from here. Not yet: `mtg.mulligan_tuck` (the tag is sent, the serve path is the entity-set
evening's leftover — routed to evening 2's opener), the sub-row distillation term (the label run's
pool lands tonight; the term is evening 2's first item with the mode fit).

## Addendum (2026-09-07, 18:30): the surface-label run — the first sub-row pool

`data/runs/b3-surflab-20260907-145656` (ingested to `data/trajectories/b3-surflab-20260907-145656`):
1,000 self-play games in 3.5 h (998 finished, 2 engine NPE crashes — the standing class), acting at
bar 0.10: act rate 9.3%; **26,083 sub rows (26/game)** — entity_one 12,381 (mean 13.3 options,
Δ ≥ 0.02 on 22.8%), order 6,335 (2.8%), mode 3,651 (22.8%), entity_set 2,280 (25.8%), scry 1,072
(11.1%), name 364 (2.2%). Misses: `mode:idx` 2,518 of 12,881 mode answers (the enumerator gaps —
repeat-allowed multisets, sizes below min — fixed before the mode fit), the rest < 2%. The pool
carries no `ak`/`sak` (its jar predates the keys); ability options key on host + kind. Headroom
by shape as the search sees it: the entity shapes and mode, not ordering or naming — the evening
order stands.

## Addendum (2026-09-07, 19:40): evening 2 OPENED — mode; the sub-row frame; fork `950f318a9e6` (forkcheck pending)

Findings from the first label pool: (a) every `mode:idx` miss was one of two enumerator gaps —
a size-1 neighbour of an empty natural under "choose exactly two", and distinct subsets under
"choose three, repeats allowed" (the Confluence family; four pool cards allow repeats); (b) **the
heuristic answers no modes in roughly half of all traced mode windows** (`CharmAi` finds no
`AILogic$Good` mode and the spell resolves with an empty choice) — the leak is shared by every
network arm in the Build 2 reads and the mode head addresses it directly, so evening 2's paired
read is the first with a plausible real strength effect; (c) no store carried ability keys, so the
modes of one host were indistinguishable to the model; (d) the distillation term had no state — a
sub row's surface happens on the copy after the forced option resolves, and only 8% (mode) to
19% (entity_one) of sub rows share their option with the mainline.

Decisions (user, 19:00): **the distillation state is the copy's surface-window frame captured
into the sub row** — `Surfaces.dec` stashes the copy's own dec record (options + obs + hist, the
wire shape the bridge already builds) on the pending `SurfaceDirective`, `match()` pins it at the
fired callback, the expansion round writes it as the sub row's `frame` (~5 KB, one per sub row);
not the parent mainline frame, not the 8% join. **The keyed pool regenerates on the evening-1
ckpt with the entity surfaces served** (the behavior policy of record; trunk frozen at day zero).
**The mode serve wire carries a repeat flag** (`Constraints.repeat`, proto3 bool, both copies;
`AnvilBridge.selectSet(…, repeat)`; validated distinct unless the callback allows repeats —
`CharmEffect.chainAbilities` clones each chosen sub). **Enumerator scope**: every non-natural
answer inside [min, max]; k-multisets under repeat; the natural's size ± 1 stays the only size
neighbourhood. The tuck serve mapping (the target decoder's entity picks → hand indices by the
`(id)` label) and the orchestrator's deadline auto-raise ride the same evening.

**The distillation term** (item 4 realized; `anvil/training/surface_distill.py`): per sub row, the
target is the leaf-value softmax over the enumerated answers at T = 0.025 (the acting rule's
temperature) restricted to answers the decoder can emit (inside [min, max], no repeats unless
allowed — the heuristic's empty Confluence answer is valued but sits below min, where STOP is
closed; it is dropped and the target renormalizes); the loss is the cross-entropy to the decoder's
within-group softmax of teacher-forced sequence log-probs (one group = one sub row; batches hold
whole groups). Set-like labels (entity_set, mode) are canonicalized to sorted index order for
both imitation and distillation from this evening.

Landed: fork `950f318a9e6` (tests 15; smoke `build3-surface-smoke-e2`: 66 sub rows, 0 misses, a
frame on every sub row, the Confluence windows enumerate the four 3-multisets) and Anvil
`0637050`. Launched 19:36–19:38: the keyed label run (`build3-surface-labels2`, 1,000 games) ∥
the forkcheck `run-20260907-build3-mode`. Rule for the term from here: **a sub row's state is
its own frame; a sub row without a frame is not a label.**

## Addendum (2026-09-07, 20:50): fork `950f318a9e6` PROVEN — fork pin

Forkcheck `run-20260907-build3-mode` (500 games, seed 20260703, the new jar) vs the 08-21 baseline:
**498/500 main-trace hashes identical** (fork fidelity 449/51 vs 450/50). The misses: 20260969 =
the standing launch-unstable crash; **20260853 replays to the baseline hash `6ec06cb75d96f2b2` on
the same jar, twice** (`replay-20260907-build3-mode-853a/b`) — the identity-hash residual class,
as on `a0ed9e314b5`. **PASS at the ADR-0025 standard → the research fork pin moves to
`950f318a9e6`.** The keyed label run (jar snapshot of the same commit) is on a proven jar.

## Addendum (2026-09-07, 23:50): the keyed pool; the key-stability bug (fork `1e17923c82c`, forkcheck pending)

The keyed label run (`b3-surflab2-20260907-193632`): 24,992 sub rows in 1,000 games, `mode:idx`
misses 0 (from 2,518), every ability option keyed, a frame on every sub row. Building the cache
with the store's side table exposed **a key-stability bug in item 8**: the `D:` line took
`sa.getDescription()`, which for an ability IN PLAY carries runtime state — a triggered ability's
bracketed run-parameter dump and the " by <source> (<id>)" attribution of granted / copied
abilities — so each instance hashed to a new key (10,325 store-only keys in 1,000 games; 427 for
one Monarch trigger). `AbilityKey.stripRuntime` (fork `1e17923c82c`) removes exactly those shapes;
static brackets stay; **the pool re-dump is byte-identical (5,148 keys)**, so every `ak` in every
store stays valid and the pinned cache is unchanged. The mode options were 90% pool keys
throughout, so evening 2's fit is unaffected; the leak mattered for triggers (Build 4's stack
entries) and for the append path's growth. Rule (standing-rules candidate on the proof): **an
ability's key is a function of its static canonical text; runtime state never enters it.** The
chain for the evening-2 checkpoint launched 23:10 on the cache with the side table folded in
(`abil-cf2ca6ba-b3s2-qwen3`, 15,473 rows; the model projects vectors, never rows, so any
superset cache serves).

## Addendum (2026-09-08, 00:20): the key fix `1e17923c82c` PROVEN — fork pin; the key-stability rule

Forkcheck `run-20260908-build3-keyfix` vs the 08-21 baseline: **498/500**; 20260969 = the standing
launch-unstable crash; **20260744 replays to the baseline hash `dbf25ab99ce90dee` twice on the same
jar** (`replay-20260908-build3-keyfix-744a/b`) — a new seed in the miss set, the launch-unstable
class. **PASS → the research fork pin moves to `1e17923c82c`.** The rule is born (standing-rules,
engine/data hygiene): **an ability's key is a function of its static canonical text — runtime
state (a trigger's run parameters, a granted ability's source attribution) never enters it; the
proof of a key-function change is the byte-identical pool re-dump.** Tomorrow's smoke and paired
read run on this jar.

## Addendum (2026-09-08, 01:00): the evening-2 checkpoint `m12-build3-e2` — the fit read and the served-head smoke

The chain (`data/runs/build3-e2/`, three surfaces, imitation on the 12 Build 2 arms + the keyed pool,
the distillation term on the keyed run's frames at T 0.025): pooled cross-fit surf_one 0.338 /
surf_set 0.450 / surf_mode 0.393 (the mode number is dominated by unkeyed labels — not a read);
**the keyed-store-only held-out mode fold: exact 0.461 (n 154) vs first-option 0.409**. Build
`data/training/m12-build3-e2/last.pt`. Served-head smoke on the key-fixed jar: 8/8 won, 0 model
errors, 45 bridged mode answers accepted (12 of them the three-pick Confluence answers with
repeats), 5 tuck answers, 238 entity answers, 0 expansion misses. The 600-game paired read (withheld
vs served: entity one + set + mode + tuck) is the evening's pre-registered read.

## Addendum (2026-09-08, 02:00): evening 2's paired read — A FLAG, attribution arms launched

`data/runs/build3-surface-read-b3e2/` (the e2 ckpt on jar `1e17923c82c`, 2 × 300 games per arm vs
the heuristic on the final_read pairs, network alone): **withheld 0.512 ± 0.021 (592 games) /
served 0.478 ± 0.021 (594); on − off = −3.24pp ± 1.87 (t −1.7, n 587 pairs, 51 up / 70 down)**
against evening 1's +2.06 ± 1.83 on the same protocol (the two evenings differ by ~5.3 ± 2.6).
No crash in either arm (the standing BridgePoisoned class absent this time); every bridged answer
accepted (entity 3,271, mode 276 — k=1 181 / k=2 84 / k=3 6 —, tuck 135). Standing rule: one
600-game read carries no strength claim; but a served set that reads below its withheld twin at
t −1.7 is the "something broke" branch of the evening's pre-registered read, and the cost sits in
the answers, not in rejections. Candidates: the tuck serve (the BC-era target-decoder head, never
served before tonight — a bad tuck costs the game early), the mode head (thin imitation +
distillation), the entity heads' refit (surf_set exact 0.465 → 0.450). **Attribution arms
launched 02:00** (`ablation.sh` in the read dir, the same seeds and reference): `notuck` = the
served set minus the tuck; `tuckonly` = the tuck alone. Read in `read-ablation.json`.

## Addendum (2026-09-08, 02:50): the attribution read — no component carries the flag

`read-ablation.json` (the same pairs and withheld reference): **`notuck` (entity one + set + mode)
0.503 — vs off −0.85pp ± 1.92 (t −0.4, 61 up / 66 down); `tuckonly` 0.513 — vs off −0.34pp ± 1.02
(t −0.3, 17 up / 19 down)**; the full set −3.24 ± 1.87 (t −1.7). The parts sum to about −1.2 where
the whole read −3.2; the gap (−2.0 ± ~2.5) is inside noise. Reading: no served component is
individually below its withheld twin beyond noise; the full-set number is one 600-game
observation of one configuration, and the standing rule says it carries no claim. Crash classes:
none new (the `tuckonly` arm's 3 BridgePoisoned = the standing serving class). Every answer
accepted in every served arm. **Evening 2's "nothing broke" read therefore holds on components;
the full-set flag is banked as an open observation**, to be resolved by the next larger read (the
post-Build-4 2,000-game read, or a repeat 600-game pair if the user wants it before evening 3).
**The served set from here is the user's call** (default, per the capabilities-over-fallback
standing preference: entity one + set + mode + tuck, the server's current advertised set; the
conservative alternative: drop the tuck, whose own read is the cleanest of the three, until it
earns a read of its own). Evening 2's assets stand: the enumerator fix, the sub-row frames, the
mode wire, the distillation term, the key-stability fix, the keyed pool, `m12-build3-e2`.

## Addendum (2026-09-08, morning): attribution — the mode head carries the flag

Two reads on the existing pairs and one new arm, all on the same seeds vs the same withheld
reference. (1) **The exposure split** of the paired diffs (games in which the served seat answered
≥ 1 mode window vs the rest): full set −6.8 ± 3.8 (n 183) vs −1.8 ± 2.1; the set without the tuck
−5.1 ± 4.0 (n 187) vs +1.0 ± 2.1; games with neither a mode nor a tuck answer −0.2 ± 2.2 (n 325);
tuck-exposed games in the tuck-only arm −0.9 ± 4.5. Two arms agree: the loss sits in
mode-exposed games (post-treatment split — attribution, not a verdict). (2) **The entity-only arm
on the e2 ckpt: 0.527, +1.72pp ± 1.91 (t 0.9, 67 up / 57 down)** — evening 1's +2.06 holds, the
entity refit with the distillation term did not cost strength. So: entity-only +1.7 → + mode −0.85
→ the mode head ≈ −2.6 ± 2.7 overall and −5 to −7 where it answers. Hypothesis for the mechanism:
the distillation target at T 0.025 over single-roll leaf values amplifies leaf noise on the common
choose-one windows (mode spread p50 0.001), where the heuristic's pick is usually right; the
Confluence gain is real but rare. Being measured: the 100-game search run with the e2 head serving
at two rolls per copy (`build3-e2-search`) — the search's headroom over the head's own picks vs
over the heuristic's, and the leaf-noise σ from roll pairs, which sets the temperature for the
refit.

## Addendum (2026-09-08, 08:50): the e2 search run — the head beats the heuristic by the leaf value and loses by the outcome; the leaf noise

`build3-e2-search` (100 self-play games, the e2 head serving entity one + set + mode, rate 1,
`-searchsurf 2`, **two rolls per copy**; 99 won / 1 draw): the search's headroom over the served
head's own picks vs over the heuristic's picks in the keyed pool —

| kind | over the e2 head: Δ ≥ 0.02 / natural is best / p90 | over the heuristic | single-roll leaf σ |
|---|---|---|---|
| mode | **0.183 / 0.585 / 0.056** | 0.297 / 0.458 / 0.113 | 0.026 |
| entity_one | 0.193 / 0.453 / 0.042 | 0.261 / 0.412 / 0.074 | 0.051 |
| entity_set | 0.135 / 0.464 / 0.031 | 0.245 / 0.408 / 0.064 | 0.054 |

By the leaf value's own yardstick the mode head is the better answerer — fewer improvable windows,
its pick already the best enumerated answer more often — and it loses the games it answers
(−5 to −7pp on exposed games in two arms). **Reading: the distillation target is the problem, not
its noise** — the head learned to maximize the one-ply leaf value, and on modes that value is not
aligned with winning (myopic: the leaf sits at the next quiescent window; a mode whose value
materializes later — a card drawn, a body vs damage — is mispriced against an immediate effect).
The entity heads survived the same term because 220K imitation labels anchored them; the mode
head's imitation base was ~750 labels, so the term dominated. The noise is also real: single-roll
σ 0.026 (mode) to 0.054 (entity) against T 0.025 — the target amplified noise on the flat windows
(mode spread p50 0.001) — but noise alone cannot produce "better by V, worse by outcome".
**Consequence for item 4 (pre-registered as a hypothesis, tested next): distilling a surface head
toward the one-ply leaf value is not safe without a strong imitation anchor; the term's temperature
must sit at or above the measured leaf σ; and the acting rule's bar 0.10 ≈ 2σ (entity) stands.**
Test launched 08:50: variant (a) `m12-build3-e2a` — the mode head by imitation only, the entity
heads distilled exactly as in e2 — served (entity one + set + mode) vs the same withheld reference
(`read-e2a.json`). If it reads at the entity-only level (+1.7), the mode distillation was the harm;
variant (b), a noise-calibrated T (≥ 0.1) at lower weight, then separates "myopic target" from
"cold temperature" if the user wants the distinction before evening 3.

## Addendum (2026-09-08, midday): the mechanism — a mode-only choice against a joint mode + target choice; the playability gate (user-approved stopgap)

Variant (a) (`m12-build3-e2a`, the mode head by imitation only, the entity heads as e2): served
(entity one + set + mode) vs the withheld reference −0.69 ± 1.90; mode-exposed games −3.9 ± 3.8.
The third mode-serving arm to lose where the head answers — the distillation target was not the
mechanism. The split by answer size, pooled over the three arms: **games with only single-mode
answers −7.3pp ± 3.2 (n 308)**, games with a multi-mode answer −2.8 ± 3.1 (n 253), games with no
mode answer +0.1 ± 1.2 (n 1,234). The loss sits in the ordinary choose-one windows the heuristic
answers, not in the ones it declines.

**The mechanism is structural.** Modes are chosen at cast time (`PlaySpellAbility` →
`CharmEffect.makeChoices`), before payment; the cast path then clears and re-chooses every target
in the chain through `chooseTargetsFor` = the AI's **mandatory** chooser. When the heuristic
answers, `CharmAi` picks a mode only when that mode's own play test passes — its mode choice is a
joint mode + target choice (served answers carry targets at the callback 8 / 82 times, the
heuristic's 70 / 156). The head's pick is mode-only; a mode the AI would not play then gets
whatever legal target the mandatory chooser finds. So on choose-one windows the head trades "a good
mode with a good target" for "a mode the head likes, aimed by a forced chooser".

**Decision (user, midday): the playability gate as the stopgap** (`Surfaces.playableModes`, fork
commit pending its smoke): the engine's own play test over the modes (`canPlaySa` per mode, the
heuristic's first pass); when any mode passes, the head's answer stands only if every pick is
playable, else the natural line (`gate=defer`); when none passes (the heuristic would decline —
the Confluences), the head answers freely (`gate=free`). Serve-only; the heuristic's own path
unchanged. Labeled a stopgap: a heuristic judgment gating a learned head.

**Routed by name (the principled replacements, in order):** (1) **mainline surface acting on
modes** (the closing evening's item, brought forward for modes): enumerate the answers, play each
on a copy through to the leaf — the copy plays the mode with its targets, so a badly aimed mode
reads as a lower leaf; the engine + the value head replace the heuristic's judgment. Caveat: the
first read is a test of the value head on modes (leaf σ 0.026/roll vs mode spreads mostly < 0.01
→ rolls ≥ 2 and a bar), since today's "best by V" number was contaminated by the head having been
trained on V. (2) **Targets as a surface**: bridge `chooseTargetsFor` for sub-abilities through
the entity surfaces so the model aims its own modes (candidates from the engine's target
restrictions; labels = the heuristic's targets; the same trace + distill machinery) — the coherent
end state, after evening 3. (3) An engine fact as an option feature: the legal-target count per
mode (legality, not judgment) so the head sees aim availability before choosing. The planner (the
D6 carry, the M10 route) is not the tool: it carries intent, not feasibility.

## Addendum (2026-09-08, 11:10): the gated read — the mode loss is gone; the ladder on one reference

`read-gate.json` (the gate jar `bc01efe1609`, the e2 ckpt, entity one + set + mode served, vs the
same withheld reference): **0.524, +1.19pp ± 1.86 (t 0.6, 63 up / 56 down)** — the entity-only
level (+1.72 ± 1.91) within noise. Gate census: **pass 94 / defer 160 / free 42** (the head's
answer stood on 46% of its windows). Exposure split: games where the head's answer was served
−2.3 ± 5.3 (n 110; −7.3 ± 3.2 ungated), games with mode windows all deferred +4.6 ± 5.2, no mode
window +1.5 ± 2.1. The ladder, all vs one withheld reference of 600 games:

| served set (e2 ckpt) | on − off |
|---|---|
| entity one + set | +1.72 ± 1.91 |
| + mode, ungated (distilled) | −0.85 ± 1.92 |
| + mode, ungated, imitation-only (e2a) | −0.69 ± 1.90 |
| **+ mode, gated** | **+1.19 ± 1.86** |
| tuck alone | −0.34 ± 1.02 |
| entity + mode ungated + tuck (the first read) | −3.24 ± 1.87 |

The remaining arm — the served set as it will be used (entity + gated mode + tuck) — runs now
(`read-allG.json`); the gate's forkcheck (`run-20260908-build3-gate`) decides the pin.

## Addendum (2026-09-08, 11:30): the gate `bc01efe1609` PROVEN — fork pin

Forkcheck `run-20260908-build3-gate` vs the 08-21 baseline: **499/500** (fork fidelity 450/50 =
the baseline's); the one miss 20260969 = the standing launch-unstable crash. **PASS → the research
fork pin moves to `bc01efe1609`** (the gate on the key fix on the evening-2 tip). The withheld
reference arm of the ladder ran on `1e17923c82c`; the served arms with the gate on this jar — the
proof says the two are behavior-identical off the bridged mode path, so the ladder reads on one
reference.

## Addendum (2026-09-08, 12:00): EVENING 2 CLOSED — the served set's read

`read-allG.json` — the served set as the server advertises it (entity one + set + gated mode +
tuck; the e2 ckpt; the gate jar) vs the withheld reference: **0.509, −0.17pp ± 1.80 (t −0.1,
54 up / 55 down)**; crash class = the standing BridgePoisoned only (5). The "nothing broke" read
holds; every component within noise of every other on one 600-game reference (entity-only +1.7,
gated mode +1.2, tuck −0.3, all −0.2 — the full set sits ~1.4 ± 2.6 below entity-only: banked as
an observation, not a claim). **Evening 2 closes with entity one + set + gated mode + tuck served.**
Assets: the enumerator fix (mode misses 2,518 → 0), the sub-row frames, the mode wire with
repeats, the distillation term (kept for the entity heads; the mode head's harm was structural,
not the term), the key-stability fix, the keyed pool + the side-table cache, `m12-build3-e2`, the
playability gate (a stopgap). Lessons for the standing rules (candidates, on the closeout): **a
served surface answer must be realized with everything the heuristic's answer bundles** — read the
engine's cast path for what the heuristic decides jointly (here: targets) before serving the
callback alone; **attribute before re-running** — split the existing paired arms by exposure
and run ablation arms on the same withheld reference (the ladder), a 600-game rerun would only
have re-flagged. Next: evening 3 = ordering + damage; routed ahead of it for the mode head:
mainline surface acting on modes, targets as a surface, the legal-target count feature.
