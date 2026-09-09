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

## Addendum (2026-09-08, 13:45): EVENING 3 OPENED — ordering + damage; fork `41ac60d6b21` (forkcheck pending)

**What the keyed pool says** ([devlog](../devlog/2026-09-08.md)): ordering's sub rows are trigger
ordering (2,726; n = 2 for 2,595 — Solitude's ETB vs its evoke sacrifice is the shape) and
move-to-zone ordering (3,069; mostly graveyard orderings where the order is irrelevant); **blocker /
attacker ordering never fires** — the engine runs the modern no-assignment-order rule
(`GameRules.orderCombatants` off); **damage has zero sub rows by construction** — a copy from a
quiescent main-phase window stops at the seat's next quiescent window (the start of combat on the
pass path), so the leaf value has never seen a damage assignment, while the mainline carries ~350
multi-blocker windows per 1,000 games. Ordering's headroom is noise (Δ ≥ 0.02 on 2.6%, p90 0.004;
single-roll leaf σ 0.065, the largest kind). Neither callback bundles a joint decision the way modes
bundled targets (trigger targets follow the ordering; the damage map is the whole decision).

**Decisions (user):** (1) imitation only for both heads — the middle rung of item 4 is skipped
where it has no signal; they reach RL in the loop through the served head's behavior logp (Build 4½
/ 5); (2) both ordering callbacks served, windows past the decoder's 12 slots on the natural line;
(3) damage ships imitation-only as a "nothing broke" component (0.35 windows per game); (4) ORDER_N
on the wire for both, damage as a **kill order** over blockers (+ the defender last under trample)
realized as amounts by the engine's own lethal arithmetic; (5) ride-alongs: the DAMAGE enumerator
family under the rule in force (every prefix of every blocker permutation, closed by the defender
under trample) and the copy-state snapshot null guard (`Player.getView()` on a controller-less
option card); (6) the evening order after this one stands (payment tag, then mainline surface
acting with modes first).

**Landed:** fork `41ac60d6b21` (`AnvilBridge.order`, `Surfaces.askOrder` / `askDamage` /
`damageFromSequence` — the remainder tramples over by `distributeAIDamage`'s rule, a defender pick
means "stop killing here" — the damage dec's defender option + `lethal` + `trample`,
`ObsSnapshot.look`; tests 16); Anvil `ee6c512` (`surf_order` / `surf_damage`, the wire answers, the
label canonicalization of the heuristic's amount map). Loader check on the keyed pool: order 5.2
windows / game, damage 0.37, 0 misses. **Launched 13:45:** forkcheck `run-20260908-build3-e3` on
the snapshot jar ∥ the fit chain `build3-e3` (five tasks, e2's recipe: the only change vs e2 is the
two new heads). Read instrument unchanged: the served-head smoke, then the 600-game paired read
(served = all six tags vs withheld), pre-registered "nothing broke" + the exposure split.

## Addendum (2026-09-08, 14:30): fork `41ac60d6b21` PROVEN — fork pin; the first folds

Forkcheck `run-20260908-build3-e3` (the evening-3 snapshot jar) vs the 08-21 baseline: **498/500**
(fork fidelity 448/52 vs the baseline's 450/50); the misses are the standing pair — 20260969 the
launch-unstable crash, 20260853 the identity-hash residual, **replayed twice on the same jar to the
baseline hash `6ec06cb75d96f2b2`** (`run-20260908-build3-e3-replay1/2`). **PASS → the research fork
pin moves to `41ac60d6b21`** (the ordering + damage serve wire, the modern-rule enumerator family
and the snapshot null guard on the gate `bc01efe1609`). The fit chain's first folds: order exact
0.742 / 0.729 (trigger ordering 0.852 against the keep-the-input-order baseline 0.770;
move-to-zone 0.645, *below* that baseline — graveyard orderings the heuristic leaves alone, the
head flips some), damage 0.381 / 0.369 (slot-0 0.597 vs first-option 0.509; n ~600 per fold),
entity + mode at their evening-2 levels (the shared trunk unmoved).

## Addendum (2026-09-08, 16:30): EVENING 3 CLOSED — ordering + damage served; the exposure split is not an instrument

**The chain** (`data/runs/build3-e3/`, five tasks, e2's recipe): pooled cross-fit order 0.732 (trigger
ordering 0.846 vs the keep-the-input-order baseline 0.774; move-to-zone 0.626 below its 0.757),
damage 0.376 (slot-0 0.607 vs first-option 0.487; n 2,841); the entity + mode heads gave up a
little to two more tasks on the shared decoder (set 0.450 → 0.429, one 0.338 → 0.330, mode 0.393 →
0.387). Build ckpt **`data/training/m12-build3-e3/last.pt`** (serves all six surface tags + tuck).
**The served-head smoke** on the proven jar: 8/8, ordering 117/117 and damage 2/2 accepted, 0
server errors, 0 null-obs frames (the snapshot guard).

**The paired read** (`data/runs/build3-surface-read-b3e3/read.json`; the e3 ckpt on the snapshot
jar `41ac60d6b21`; off = the server withholding the surfaces + tuck, on = all six + tuck; 2 × 300
per arm vs the heuristic): off 0.504 / on 0.503, **on − off +0.52pp ± 1.82 (t 0.3, 57 up / 54
down, n 580)**; crash class = the standing BridgePoisoned only (4 per arm); served census on the
on arms: trigger ordering 741/741 accepted, move-to-zone 844/844, damage 61/61 (k = 1 for 23, full
kill orders otherwise), mode gate pass 96 / defer 150 / free 45. **"Nothing broke" holds — evening
3 closes with ordering + damage served; the served set from here is entity one + set + gated mode
+ tuck + ordering + damage.**

**The exposure split is selection, not effect (a lesson for the instrument).** Keyed on the ON
arm's game (the standing use, evening 2): trigger-ordering-exposed +9.6 ± 2.5 (t 3.8) / unexposed
−6.9 ± 2.5; keyed on the OFF arm's game instead: exposed −2.2 ± 2.7 / unexposed +3.0 ± 2.4 —
**the sign follows the conditioning arm** (damage: +10.0 ± 6.0 vs −13.9 ± 7.1). A window that fires
when the seat's board survived (two of its triggers at once; a multi-block on its attacker)
selects that arm's better games: the split conditions on the outcome path. The symmetric key (the
window fired in both arms' games) reads exposed +4.7 ± 2.3 / unexposed −6.3 ± 2.9 — still a
length selection, exploratory. Evening 2's mode attribution stands on the ablation arms on one
reference (entity-only +1.7 vs + mode −0.85, the ladder), not on its exposure split, which had the
same structure. **Standing rule born here → standing-rules.md (gating/reads): an exposure split
keyed on one arm's own game is post-treatment when exposure correlates with survival; attribution
is ablation arms on one reference; a split is exploratory and, if read at all, keyed symmetrically.**
`scripts/surface_exposure_read.py` carries the caveat and the `--key fired --arm both` key.

Assets: fork `41ac60d6b21` (pinned), `m12-build3-e3`, `surface_served_census.py`,
`surface_exposure_read.py`. Routed by name: a fresh keyed pool on this jar (the new damage dec
shape; stable keys) at the next label regeneration; search from combat windows (the leaf value
reaching damage) with mainline surface acting or Build 4½; the move-to-zone head's below-baseline
agreement (inert on graveyards, watched on library put-backs) — the closing evening's per-callback
serve switch if a read ever needs it. **Next: evening 4 = the payment tag (the ADR-0102 rescue
class: the enumerator + distillation into the pay head), then evening 5 = mainline surface acting
(modes first).**

## Addendum (2026-09-08, 19:35): EVENING 4 OPENED — the payment tag; fork `e44d83a8327` (forkcheck pending)

**The facts the evening starts from.** (1) **The pay head has never been trained**: every M12
checkpoint (the day-zero `m12-build1-stopstate`, e1–e3) carries the payment parameters at their
design init (`pay_bias` +2.0, `pay_kind_emb` / `pay_mark_emb` zero); in the evening-3 on arm it
bridged 2,805 consequential windows / 300 games (9.4 per game) and picked auto in 97.3% — the 76
goal picks are the untrained pointer's, not judgment (every one executed `directed_ok`). (2) **A
search copy bridged the pay tag too** (GameCopier keeps the seat's bridge and tag set): the head's
random deviations were leaf noise inside every copy of every read since Build 2. (3) **Imitation is
empty here, not just banned**: the heuristic's answer is auto = option 0 = the head's init; the M9
pin (no BC from the heuristic) stands and costs nothing; the only label that can move the head is a
counterfactual one. (4) The traffic and the headroom (ADR-0075): 9.4 bridged consequential windows
/ game, forced 0.1 / game, **certifiable 0.32 / game at +9.2pp per window → ≈ +3.0pp / game at
perfect play** — the largest measured headroom on file, concentrated in ~3% of the windows; most
consequential windows are ties. (5) The ADR-0077 payment-completion queue is mostly closed
(ADR-0083 landed cousins / costmod / pool-tie; cost-modified windows still auto-paying are 4.7% of
in-scope windows today, not the recorded quarter); the open item is **resolution-effect payments**
(51 / game in today's census, all unbridged, consequential fraction never measured).

**Decisions (user-adjudicated 2026-09-08 evening).**

1. **The asymmetric distillation target.** A leaf-value softmax over a tie window is near-uniform
   and a KL toward it teaches random deviation (evening 2's mode failure). The target is **auto
   unless a goal clears a margin bar over auto by leaf value** (then the softmax at T over the
   valued answers, auto included); **rolls ≥ 2** (single-roll leaf σ 0.026 against a 3%
   positive population). Ties and positives are read apart, never blended (ADR-0069).
2. **The end-of-turn leaf for payment answers.** A payment's consequence is not at a later decision
   of ours but downstream of the natural line — the next spell this turn, or what is open on the
   opponent's turn — so the pinned next-quiescent-window leaf (right after the spell resolves) sees
   nothing. The payment expansion values every answer, the natural one re-run, at **the seat's
   first quiescent window of a later turn** (ADR-0098's eot horizon, K=1 ≈ K=8 there); a
   per-surface leaf setting. **Not depth**: a deeper tree ending at the same one-ply evaluator
   (Spearman 0.39) inherits its ceiling and multiplies copies at windows where the class changes
   nothing; horizon and variance are the levers, spent in the offline pool. The instrument that
   says whether this leaf ranks payments is the **horizon-2 certify rollout on a sample**
   (Spearman of the one-ply spread vs the rollout win-diff, eot vs next) — the calibration read,
   never the label source.
3. **The copy-side pay gate.** A search copy never bridges its payment windows (the natural line
   is the engine's auto payer) unless the payment surface itself is being expanded;
   `-searchpaybridge` restores the old behaviour for later, when a trained head is the natural
   line. A correctness fix for every read.
4. **The payment surface has its own expansion slot.** A payment fires at cast, before any other
   surface, and would crowd the entity / mode / ordering surfaces out of the single first-traced
   slot; `-searchpay B` expands the first traced payment window on the top-B paths beside
   `-searchsurf`'s slot, under the same budget accounting.
5. **The rescue class as its own flag-gated bundle, second commit, own arm.** Admitting
   enumerator-payable casts to the mask AND making the directed plan the natural line at that
   window (an admitted-by-enumerator cast paid by auto fails at apply — ADR-0102's veto) are one
   game-path change, forkcheck-proven with the flag off, read as the third rung of the evening's
   ladder (withheld / head / head + rescue) on one reference. Shadow cost +19% engine time.
6. **Serve with a margin bar**: after the fit the served head deviates from auto only where its
   log-prob margin over auto clears a bar (`--pay-bar`), the acting-rule shape.
7. **The queue: nothing widened this evening.** Resolution-effect payments route to **the second
   payment touch = the Build 4½ opener** (after the Build 4 re-warm and the post-Build-4 day-zero
   re-read, before the shakedown), **conditional on this evening's target validating** by the
   horizon-2 calibration; if it does not, to the closeout with the reason "the genre's target is
   unproven on the simpler genre". The measured argument the second deferral owes is paid this
   evening for free: `-paytelemetry` now records one census row per resolution-effect window
   (goals / plans / consequential / auto-payable / costmod over the raw cost; zero-cost counted).
   First sample (smoke 2, 8 games): **170 / 170 resolution-effect windows are zero-cost** — the
   label run's 1,000 games decide.
8. **What "train enough" means.** Not "nothing broke" alone: a learnability read on the population
   that matters — does the fitted head deviate where a goal clears the bar (positive top-1 and
   deviation rate up from 2.7% random), stay auto on ties, and does the paired sign land positive
   even under noise. Strength is the big run's; the head enters the loop with a target shown to
   point the right way, or the target goes back to the table before the loop is asked to learn it.

**Landed: fork `e44d83a8327`** (on `41ac60d6b21`): `Surfaces.PAY` (kind 7: {auto} ∪ the M9 goal
options, one pick; the enumerator = every index, natural first), `PlayerControllerAnvil.copyPay`
(the acting seat's consequential windows on a copy: the M9 enumeration exactly as the mainline
path, the wire-shaped dec record on the copy's session = the sub row's frame, a PAY
`SurfaceDirective` answered with a goal index through the directed executor, every window traced
with natural = the pick), the copy-side gate (`copyPayBridge`, default off), `SearchDirective
.leafAfterTurn` + `window(options, quiescent, turn)` (the eot leaf), `AnvilRun -searchpay B
-searchpayleaf eot|next -searchpaybridge` with the pins on the search header, `expandRound` (the two
slots through one helper; the natural answer re-run under the eot leaf; `"leaf"` on the sub row),
the resolution-effect census row; `SurfacesEnumerateTest` 17 — **the two evening-3 damage
assertions had never passed** (a kill order realizes amounts per blocker, so (1,0) and (0,1) both
read [2,3,1]; the stale-per-class-report trap) and are corrected here. Serve / recording /
search-copy only (ADR-0025-exempt, forkcheck pending). Smokes (8 games each, rate 0.3, rolls 2,
`-searchpay 2` eot): pay sub rows with frames on every row, directed copies `directed_ok` 554 /
554, 0 misses; the leaf values differ across goals on most windows (a first-window tie was the
exception); cost ≈ 4.9 pay copies per searched window at ~25 asks each (≈ 4× the first ply).
**Anvil**: `anvil/training/pay_distill.py` (the asymmetric target, ties / positives apart,
`collate_pay`, `pay_distill_loss` over the pay head's candidate softmax), `anvil/training/pay_fit.py`
(cross-fit by game seed, `--unfreeze pay` = the 4,624 payment parameters, before / after reads,
`--build`), the server's `--pay-bar` (the pointer logits now on `act`'s return), the census reader's
payment rows, the label script's PAY / PAYLEAF / PAYTEL / TAGS knobs.

**Launched 19:33–19:34**: the forkcheck `run-20260908-build3-e4` (the snapshot
`data/runs/build3-e4/forge-b3e4.jar`, sha `5b01fe00…`, 500 games, seed 20260703; watchd
`forkcheck-b3e4`, notifies) ∥ **the payment pool** `build3-surface-labels3` (1,000 games, the e3 ckpt
serving every surface + tuck with **the pay tag withheld** on the mainline — the natural line is
auto and the head is untrained; `-searchpay 2 -searchpayleaf eot -searchrolls 2 -searchsurf 2
-searchsurfcap 8 -searchact 0.10 -paytelemetry`, seed base 20260909, jar = the snapshot; watchd
`build3-b3-surflab3`, notifies; ≈ 6 h at the smoke's per-window cost). Next: the forkcheck read →
pin; the pool read (positives per game at the bar, the resolution-effect census); the pay fit
(cross-fit) → build `m12-build3-e4` → the served-head smoke with `--pay-bar` → the paired read
(withheld = the e4 ckpt with the pay tag withheld, served = + the pay tag); the rescue bundle as
the second fork commit; the horizon-2 calibration on a sample.

## Addendum (2026-09-08, 19:50): the rescue bundle `c26e99824b8` (forkcheck queued); the overnight chain

**Fork `c26e99824b8`** (on `e44d83a8327`): the ADR-0102 rescue class, flag-gated — `-payrescue`
(`AnvilOptions.PAYRESCUE`, `"payrescue":true` on every header). With the flag on: an option the
auto-payer's predicate rejects but the M9 enumerator can pay is ADMITTED to the mask, the realizer's
payability accepts it (`payableOrRescue`), and a forced window (auto cannot pay, a plan exists) pays
DIRECTED by the enumerator's first plan wherever the answer would be auto — an unbridged seat's
window (`rescuePay`), a bridged seat's auto pick, a copy's natural pick. Off = byte-identical
(every path under the flag; the forkcheck `run-20260908-build3-e4r` queued behind the evening-4
one, flag off). **Smoke** (8 bridged games, pay withheld, no search, flag on): 8/8 won; per
window 28,878 options scanned / 6,326 rejected by the predicate (22%; ADR-0102's 23%) / **457
admitted** (7.2% of rejected; ADR-0102's 9.4%); **3 rescue payment windows reached, 1 paid, 2
`directed_fail`** — the admitted casts are rarely chosen, and when they are the enumerator's plan
over the raw cost does not always pay the cost as realized (the ADR-0102 veto class re-appears
as a directed failure → the re-ask); the rescue arm's veto census is the read.

**A test finding, not a regression.** `PaymentWiringTest` (the M9 Signet-chain wiring) failed 2/3
when run in one surefire JVM after `SurfacesEnumerateTest,PaymentEnumeratorTest`, and passes 3/3
alone on the same tree and 3/3 on a worktree of `41ac60d6b21`: the auto-payer's reservation check
draws from the game RNG (the ADR-0102 finding), so the class's verdict follows the JVM's stream.
Memory: run a suspect fork test class alone before calling a regression.

**The overnight chain** (`scripts/build3_pay_chain.sh`, watchd `build3-paychain`, notifies): waits
for the pool's DONE → the pool read (`pool-read.md`: usable groups / game, the margin quantiles,
positives at bars 0.01–0.08, the resolution-effect census) → `pay_fit` 5 folds (bar 0.03, T 0.025,
rolls ≥ 2, 3,000 steps, the 4,624 payment parameters) → `payfit-read.md` → the build
`data/training/m12-build3-e4/last.pt` → the served-head smoke (8 games, `--pay-bar 0.2`) → the
paired read `build3-surface-read-b3e4` on the rescue snapshot `forge-b3e4r.jar` (flag off unless
armed): **off** = the pay tag withheld (surfaces + tuck served), **on** = + the pay tag at the bar,
**rescue** = on + `-payrescue`; 2 × 300 per arm. Pre-registered: nothing broke (crash classes,
misses, the rescue arm's veto rate) + the learnability read (positive top-1 / deviation vs tie
deviation, before vs after, cross-fit) + the signs banked (on − off, rescue − on). The
horizon-2 calibration (the certify path on heuristic games with `-searchseats` + the pay slot)
is a separate small run, routed to the next session.

## Addendum (2026-09-08, 20:15): fork `e44d83a8327` PROVEN — fork pin; the e4r forkcheck running; the ablation arm routed

Forkcheck `run-20260908-build3-e4` (the snapshot `forge-b3e4.jar`, 500 games, seed 20260703 vs the
08-21 baseline): **499/500 main-trace hashes identical; the one miss = 20260969, the standing crash**
(turns 27 vs 29, the same seed as every Build 3 forkcheck); fork fidelity 450/50 both — **PASS; the
research fork pin moves to `e44d83a8327`** (the payment surface kind, the copy-side pay gate, the
eot leaf, the pay slot, the resolution-effect census row; serve / recording / search-copy only).
The rescue bundle's forkcheck `run-20260908-build3-e4r` (flag off) runs behind it. **Routed (user):
the served-tag ablation arm** — the e3 ckpt with the pay tag withheld vs the evening-3 on arm, 2 × 300
on the standard pairs, queued behind the pay chain (`data/runs/build3-e3-nopay/`); the standing rule
(served-tag parity) written; the ADR-0104 addendum carries the day-zero correction's slot.

## Addendum (2026-09-08, 20:55): the rescue bundle `c26e99824b8` PROVEN — fork pin

Forkcheck `run-20260908-build3-e4r` (the snapshot `forge-b3e4r.jar`, sha `c92ccc08…`, the flag off;
500 games, seed 20260703 vs the 08-21 baseline): **499/500 main-trace hashes identical; the one miss
= 20260969, the standing crash** (turns 27 vs 29); fork fidelity 450/50 both — **PASS; the research
fork pin moves to `c26e99824b8`** (`-payrescue` flag-gated: every rescue path under the flag, off =
byte-identical, as designed). The evening-4 paired read's rescue arm runs on this jar with the flag
on — a game-path change by design, read as its own arm.

## Addendum (2026-09-09, 13:10): the pool read; the pay-only head cannot learn the positives; the pay ROLE-COPY head (user-adjudicated)

**The pool** (`b3-surflab3-20260908-193402`, 1,000 games): 42,638 usable payment groups (42.9 / game) at
the eot leaf; margin p90 0.016 / p97 0.057 / p99 0.137; **positives at bar 0.03: 5.7%** (ADR-0075's
3.2% certifiable between the 0.05 and 0.08 bars). Directed copy payments 249,044 ok / 733 fail
(0.3%) / 182 salvage. **Resolution-effect census: 48,758 windows, 99.2% zero-cost, 230 consequential
(0.23 / game, all auto-payable) vs 9.4 mainline windows — the ADR-0077 queue item's measured
argument (≈ 2% of payment decision traffic).**

**Label reliability (split-half over the two rolls, positives):** best-goal agreement between rolls
**0.648 vs chance 0.260**; both rolls clear the bar independently 0.582; auto best in either roll
0.175. The positives are mostly real; more rolls would sharpen them, not change the verdict.

**The cross-fit (pay-only params: `pay_bias` + `pay_kind_emb` + `pay_mark_emb`, 4.6K; bar 0.03, T
0.025, lr 1e-3, 3,000 steps), folds 0–3:** CE 0.45–0.50 → 0.38–0.44 **by moving toward auto** —
pos_top1 0.01–0.02 before AND after, pos_dev 0.03–0.07 → 0.01–0.05, tie_dev 0.03–0.04 → 0.015–0.018.
**The pay-only head cannot represent a positive**: its answer is mostly one goal among goals of the
same kind, and the trainable path (a kind embedding added to a frozen entity key, dotted with a
frozen state query) ranks kinds against auto, never entities. Not the data (2.4K positives, free
from the search slot at 2.4 / game), not the target (reliable), the capacity.

**Decision (user, 13:05): the payment ROLE-COPY head** — `pay_query` / `pay_key` initialized as
copies of the priority pointer's `ptr_query` / `ptr_key` and used for `pay_class` windows only,
trained on the pool with the pay pieces (the evening-1 pattern: `surf_query`/`surf_key` from the
target decoder): entity ranking capacity (525K params), day-zero identical on every window (the
copies compute the same function; a test), no drift on priority / value / surfaces. The trunk-unfreeze
variants (`--unfreeze 2` / `4` on fold 0, running) stay as the capacity probe only — a warm-start
question: in the loop (Build 4½) everything trains jointly under the KL guard. Built on a worktree
(the chain imports from the main tree). The chain's pay-only build serves ≈ auto under the bar: its
paired read is the "nothing broke" read + the rescue arm's first read; the role-copy head gets its
own cross-fit → build → smoke → paired read as evening 4's second half.

## Addendum (2026-09-09, 15:15): the evening-4 paired read (the pay-only build) — the tag itself costs; the rescue class barely fires

`build3-surface-read-b3e4` (the e4 pay-only build on the rescue snapshot `forge-b3e4r.jar`, 2 × 300
per arm; off = the pay tag withheld, surfaces + tuck served; on = + the pay tag at `--pay-bar 0.2`;
rescue = on + `-payrescue`): off 0.531 / on 0.502 / rescue 0.498 — **on − off −2.91 ± 1.85 (t −1.6)**,
**rescue − off −3.42 ± 1.90 (t −1.8)**, rescue − on ≈ −0.5 (noise). The on arm's head deviated on
**0.137 windows per game** (81 `directed_ok`, 0 failures) and the deviation-free games (n 536) read
the same −2.8: **the cost is the bridged path, not the answers** — with the served-tag ablation
(+2.56 ± 1.88 withholding the init head) that is two independent reads of one ~2.7pp effect
(combined t ≈ 2.1). The bridged path's only difference on a window the head answers auto is the
M9 enumeration + the auto-payability probe (`canPayManaCost` in test mode: `MyRandom.percentTrue`
per candidate source and AiCardMemory reservation-set clears / writes) before the same auto
payment. **The probe-path arm** (the tag bridged, the server answering auto on every window —
`--pay-bar 100`) runs now on the same seeds against the off arm: ≈ −2.8 → the probe is the cost
(fork fix: a scratch RNG + a memory-set snapshot around the probe, serve-only); ≈ 0 → two noise
reads of a small deviation cost. **The rescue class barely fires:** 20,892 options admitted over
169,033 scanned windows (0.12 / window) but only 26 rescue payments in 300 games (0.09 / game;
forced 90) — the network rarely picks an admitted cast; vetoes 460 vs 426 (+8%). Its read is
inseparable from the tag's cost at this n; the bundle stays flag-gated and off by default.

## Addendum (2026-09-09, 15:30): the set-keyed head's cross-fit; the probe fix `15863de0b4a`

**The set-keyed role-copy head, 5-fold cross-fit (pos-weight 8, bar 0.03, T 0.025, rolls ≥ 2, lr
3e-4, 3,000 steps; 529,936 trainable = `pay_query`/`pay_key` + the pay pieces), pooled over
42,638 rows / 2,423 positives:** pos CE 6.18 → **2.22**, pos top-1 0.011 → **0.094**, pos dev 0.026 →
**0.155**, tie CE 0.088 → 0.283, tie dev 0.022 → 0.045. The first head whose argmax leaves auto
where the search says to, consistently across folds (fold 0 read the same); the build
`m12-build3-e4s` follows. Its paired read waits for the probe fix below (both arms on one jar).

**The probe fix — fork `15863de0b4a`** (on `c26e99824b8`): `PlayerControllerAnvil.quietProbe` wraps
the M9 enumeration and the auto-payability test on every bridged in-scope window (the mainline
path, `copyPay`, `rescuePay`, the resolution-effect census) in a scratch RNG and a snapshot /
restore of the AI's mana-reservation memory sets — `ComputerUtilMana`'s test-mode payment draws
`percentTrue` per candidate source and clears / writes those sets before the real auto payment,
so a bridged seat answering auto everywhere still played a different game (the ADR-0102 scan rule
applied to payment). Bridged-path only; smoke 8/8 (123 windows, 0 errors); forkcheck queued
behind the wiring test. Whether it is THE mechanism is the probe-path arm's verdict (running);
either way the probe is now neutral, and the set-key read runs on this jar: off (withheld) is
unaffected by the fix, so off arms stay comparable across jars.

## Addendum (2026-09-09, 15:45): the probe path IS the cost — the auto-only arm

`build3-e4-autoonly` (the e4 build, the pay tag bridged, the server answering auto on every window
via `--pay-bar 100`, the same seeds / pairs / jar as the b3e4 arms): **autoonly − off = −2.91 ±
1.86 (t −1.6, 51 up / 68 down)** — identical to on − off (−2.91, 50 / 68) with ZERO head deviations.
Three reads now point one way: withholding the init head +2.56 ± 1.88; serving the pay-only head
−2.91 ± 1.85; bridging with auto-only answers −2.91 ± 1.86. **The bridged path's probe — the M9
enumeration + `canPayManaCost` in test mode on every in-scope window, drawing the game RNG per
candidate source and clearing / writing the AI's reservation memory — costs ≈ 2.7pp by itself.**
Every M12 network arm carried it (Build 1 onward); the D4 payment runs of M9 carried it too (a
suspect for the §3c head "never acquiring discrimination" — its baseline was the perturbed path).
Fork `15863de0b4a` (`quietProbe`) removes it; the proof is the next read on that jar: off / on (the
set-keyed head) / autoonly — autoonly − off ≈ 0 says the fix holds, and on − autoonly is then the
head's own effect on one reference.

## Addendum (2026-09-09, 16:05): the probe fix `15863de0b4a` PROVEN — fork pin

Forkcheck `run-20260909-build3-e4p` (the snapshot `forge-b3e4p.jar`, sha `86289995…`; 500 games, seed
20260703 vs the 08-21 baseline): 498/500 main-trace hashes identical — 20260969 the standing crash,
and **20260744 the identity-hash residual**: replayed twice on the same jar, replay a reproduces the
baseline hash `dbf25ab99ce90dee`, replay b the candidate's `0b119cbf37bdab27` (the same seed, the
same two hashes, on the 09-08 key-fix forkcheck) — nondeterministic across JVM launches, not a
game-path change; fork fidelity 448/52 vs 450/50. **PASS; the research fork pin moves to
`15863de0b4a`** (`quietProbe`: the payment probe RNG- and memory-neutral on every bridged window;
bridged-path only). The set-keyed head's read on this jar (off / on / autoonly) is running.
