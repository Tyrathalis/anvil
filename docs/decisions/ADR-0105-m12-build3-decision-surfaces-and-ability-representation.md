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
