# Observation schema v1 + trajectory store v0 (M1 D1)

**Date:** 2026-07-04. **Anchors:** [m1-bc-plan.md](m1-bc-plan.md) D1; [ADR-0004](../decisions/ADR-0004-m1-scope.md) decisions 1–2 (featurization line, labels-for-everything); design §1 (cross-game hygiene), §2 (entity tokens), §4 (belief head, M2), §9 (trajectory store); [bridge-protocol-v0.md](bridge-protocol-v0.md) (`observation: bytes` socket); [playercontroller-override-plan.md](playercontroller-override-plan.md) (decision surface).
**Question answered:** what the Java worker writes per decision, in what container, and how Python reads it back — such that feature iteration never forces corpus regeneration, the same record rides the bridge at eval (D8), and M2's belief head finds its ground truth already logged.

## Decisions

1. **Records are JSONL; container is per-game zstd frames.** The serializer extends the census logger's idiom (hand-built JSON lines, synchronized static writer, game-thread). JSON keeps records debuggable and schema-flexible (a new field is additive, no codegen); zstd is what makes it affordable — consecutive observations are near-identical and the plan's ~100–200GB target already priced that in. Protobuf was considered (one codec for log + wire) and declined: the `observation: bytes` field is opaque, so the *same JSON bytes* ride it at D8; a binary schema would buy ~2× raw-size for codegen coupling on exactly the records we most want to eyeball during D3/D5 debugging.
2. **Full-state records, per-entity visibility, perspective enforced in Python.** The worker logs the whole game state (both hands, real identities of face-down cards) with visibility annotations; the tensor transform drops/aggregates entities hidden from the deciding player. Forced by two facts: replay drift (ADR-0003) means whatever isn't logged now is gone, and the M2 belief head (§4) trains on exactly the hidden ground truth a perspective-filtered log would discard. The risk (an information leak via transform bug) gets a dedicated test: the transform's output for player A must be invariant under permutation/substitution of entities invisible to A.
3. **`dec`/`ret` record split.** The observation is captured at callback *entry* (some callbacks mutate state during delegation — `playTrigger` plays the trigger); the heuristic's answer is written at *exit* as a separate small record joined on `s` (sequence). This handles nested mid-resolution callbacks (census: stack depths to 23+) with zero buffering, at the cost of a reader-side join the store does once.
4. **Observations at every callback, labels best-effort v1.** Every wrapped `PlayerController` method logs a `dec` record with observation; non-void methods also log `ret`. Return values serialize by type (entity → id, collections → id lists, primitives/enums direct, else truncated string) — exact for the rung-1 one-field tags by construction, best-effort for families whose heads are M2-era. `CastPlan`-shaped priority labels are D2's extractor (census: targets/X/modes never surface as callbacks). This realizes ADR-0004's "labels for everything, heads for the rung" as far as is mechanical; construct-shaped answers (combat maps) get their serializers when their rung arrives, on the same corpus schema.
5. **Libraries are not serialized.** Own-library-as-remaining-counts (§2) is derivable at transform time: decklist (via deck name + pool manifest) minus owned, token-flagged entities observed in logged zones. Saves ~2×90 entities per observation — the difference between ~4KB and ~10KB records. Known-position library cards (scry-to-top) are a v1 gap, noted for v2 entity promotion; the scry decisions themselves are still logged. Sanity check for the derivation (tokens, copies) rides D3's label-sanity pass.
6. **Schema version at frame granularity.** `"sv":1` lives in each frame's `game` header record, in `run.json` (`obs_schema`), and in the store manifest. Records never travel without their frame, so per-record stamping (the plan's letter) is satisfied at the frame header (its intent) without 4GB of repeated bytes.
7. **No delta/dedup encoding in v1.** Full observation per `dec` record; D3 measures bytes/game and the serialization g/h haircut. Named fallback levers, in order: (a) state-stamp ref-dedup (`"ref":<seq>` when state is provably unchanged — also the convoke/improvise-loop mitigation), (b) keyframe+delta frames. Neither lands unless D3 says so.

## Record catalogue (one JSON object per line, per-game zstd frame)

Every frame is self-contained: `game` header first, `end` last. Player fields (`p`, `c`, `o`, `ap`) are indices into the header's `players` array. Absent = false/0/null/empty everywhere (size discipline).

```jsonc
// header — one per frame
{"k":"game","sv":1,"g":42,"seed":-618...,"fmt":"Commander",
 "players":[{"name":"Anvil(1)-Deck","deck":"Deck","profile":"Default","cmd":["Atraxa, Praetors' Voice"]}, ...]}

// decision — at callback entry, observation included
{"k":"dec","s":17,"t":3,"ph":"MAIN1","p":0,"m":"chooseSpellAbilityToPlay","d":23,
 "by":"bridge",                    // only on bridged answers (PlayerControllerAnvil); absent = heuristic
 "args":{"validTargets":4,"min":1},// census-style cheap summaries, method-specific
 "opts":["pass","Sol Ring ..."],   // only where options are materialized (bridged tags now, more with D2)
 "obs":{ ... }}                    // see below

// return — at callback exit, joined on s
{"k":"ret","s":17,"v":{"e":81,"sa":"Sol Ring - artifact cast"}}

// end — one per frame
{"k":"end","status":"won","winner":0,"turns":21,"ms":5804,"draw_clock":false}
```

### The observation object

```jsonc
{"glob":{"turn":3,"ph":"MAIN1","ap":0,"mono":1,"init":0,"day":"day"},   // mono/init/day absent when unset
 "players":[{"life":38,"cnt":{"POISON":1},"mana":{"W":1,"C":2},"lands":1,
             "hand":5,"lib":89,"cmdcast":[1],"lost":1}, ...],            // one per seat, header order
 "ents":[ ... ],                                                         // sorted (zone, entity id); order non-semantic
 "stack":[{"e":123,"c":1,"lbl":"Lightning Bolt ...","tgt":[{"e":5},{"pi":0}]}]}  // top-first
```

Seat indices come from the engine's *registered* players, never its live player
list — the live list drops eliminated players and reindexes, which would corrupt
every player reference in late-game records (found by the first smoke run).
Eliminated players stay in `players` with `"lost":1`.

Entity (battlefield, hands, graveyards, exiles, command zones; libraries omitted per decision 5):

```jsonc
{"e":81,               // engine entity id, stable per game
 "n":"Sol Ring",       // card identity (canonical pool name); present even when hidden — vis gates it
 "z":"battlefield","c":0,"o":0,
 "tok":1,              // token/emblem-ish: not in any decklist (library derivation must skip)
 "tap":1,"sick":1,"phz":1,"fd":1,
 "dmg":2,"pt":[4,4],   // pt when currently a creature (also the animated-manland signal)
 "cnt":{"P1P1":2},"att":80,               // counters; attached-to entity id
 "atk":{"pi":1},"blk":[9],                // combat: defender ref; blocked-attacker ids
 "vis":"c"}            // only when deviating from zone default (see below)
```

**Visibility defaults by zone:** battlefield/graveyard/exile/stack/command → public; hand → controller-only; (library → none, unlogged). `vis` is logged only on deviation: `"all"` (revealed hand card), `"c"` (face-down battlefield/exile — controller knows), `"none"` (face-down exile nobody may inspect). The transform's information-set rule: perspective player P sees `n` iff the effective visibility includes P; invisible entities collapse into (zone, controller) count aggregates. Hidden-zone ground truth thus stays in the record for M2 belief labels without ever reaching the M1 policy input.

### CastPlan labels (M1 D2 amendment, 2026-07-04)

The priority window's `dec`/`ret` pair is upgraded into the CastPlan composite label ([m1-bc-plan.md](m1-bc-plan.md) D2; census: targets/X/modes/optional costs never surface as callbacks, so they must be read off the chosen SA at decision time).

```jsonc
// dec for chooseSpellAbilityToPlay now carries structured opts: the
// engine-legal option set (same scan as the bridged path — legal, payable
// spells + land drops), materialized because replay drift forbids
// recomputing legality later and the gate metric's single-legal-option
// exclusion needs it. Pass is NOT an entry; a null ret is the pass.
{"k":"dec", ..., "m":"chooseSpellAbilityToPlay",
 "opts":[{"e":81,"sa":"Lightning Bolt ...","kind":"spell"},
         {"e":70,"sa":"Play Mountain","kind":"land"}], "obs":{...}}

// ret: the chosen SA list (usually one), CastPlan-shaped. Applies to every
// SpellAbility-valued answer (getAbilityToPlay, chooseModeForAbility, ...).
{"k":"ret","s":17,"v":[
 {"e":81,"sa":"Lightning Bolt ...","kind":"spell",   // host entity + debug/join string
  "tgt":[{"e":5},{"pi":0},{"e":123,"stk":1}],        // observation idiom; stk = targets a
                                                      //   stack SA (joins on stack host id)
  "x":3,                                              // getXManaCostPaid, absent when unset
  "alt":"Flashback",                                  // AlternativeCost, absent when none
  "opt":["Kicker1"],"mk":2,                           // OptionalCost names; multikicker count
  "modes":[{...}],                                    // chosen modes IF bound at decision time
  "sub":[{"i":1,"tgt":[{"e":9}]}]}]}                  // sub-ability chain links with own targets
```

Facts the shape encodes (census-proven, archaeology-verified): the returned SA already **is** the optional-cost copy (`GameActionUtil.addOptionalCosts`), so `opt` reads off it; X and targets are pre-set during `canPlaySa` evaluation; `modes` is usually **absent for cast spells** — they bind later at `chooseModeForAbility`, which is its own labeled `dec`/`ret` (mode subs serialize CastPlan-shaped too, carrying their targets). Option entries match the chosen plan at host-entity level. The option scan iterates `getOriginalAndAltCostAbilities(getSpellAbilities(...))` — the AI's own iteration set — so alternative/additional-cost variants are payability-checked individually; a spell payable *only* via its alternative cost (Snuff Out's 4 life) must be an option or the logged legality mask would forbid the heuristic's own pick (caught by the D2 smoke validator on the first 20-game batch).

**D2 smoke measurements (2026-07-04, 20 pool games, single worker).** Validator: 9,547 windows / 860 cast labels, zero errors. 42 KB/game at 75× (500K ≈ ~21 GB; the options lists are the growth over D1's 28 KB). Determinism, measured three ways: **same-seed runs with logging on reproduce outcomes 20/20** — the only record diffs are mana-payment micro-order (`payManaCost`/`chooseColor` land-tap order, 3/20 frames, ADR-0002's identity-hash floor; payment is engine-default per §3c and unlabeled, so corpus-harmless. **But the option scan is *not* a pure observer** (that D1 claim now covers the serializer only): same seeds with vs without `-obs` diverge 6/20 with winner flips — the scan changes *which* deterministic trajectory a seed plays, without informing the AI (ordering/tie-break perturbation, not signal). Consequences: corpus games replay only under the same logging configuration (harness `replay` now passes `-obs` for obs runs), and the with-obs and without-obs game distributions are the same policy but different draws. **Cost flag for D3:** obs+scan haircut measured **+52% single-worker** on identical-trajectory games (D1 serialization alone: 4.3% — the legality scan duplicating the AI's own availability work is the cost); D3 measures at w=16 and decides whether to share the AI's scan instead of re-running it. Bridged-path (M0) opts stay plain strings with `"pass"` at index 0 — readers distinguish by entry type. Validation contract lives in `anvil/store/castplan.py` (`python -m anvil.store validate`): host/targets ⊆ own observation, chosen ∈ options, label matches the following `playChosenSpellAbility` window per seat.

**Magic vocabulary is data, not schema** (§1 hygiene): zone strings, phase names, counter names, method names, tag names are opaque vocabularies to the store; only `anvil/encoder`'s transform (behind the `mtg.` namespace) assigns them meaning. The envelope keys (`k`,`s`,`g`,`ents`,`glob`,`players`,`obs`,`vis`,...) are game-agnostic.

## Worker output and store v0

**Worker side** (`-obs <path>` on `forge anvil`): `obs.zst` — concatenated independent zstd frames, one per game, plus sidecar `obs.idx.jsonl` — one line per game: `{"g":i,"off":n,"clen":n,"rlen":n,"seed":s,"recs":n}`. A frame is flushed/finished at `endGame`; a crashed game leaves a truncated final frame that ingest drops (the harness re-issues the game anyway). zstd level 3, `zstd-jni` on the forge-ai classpath.

**Store side** (`uv run python -m anvil.store ingest <run-dir>`): consolidates worker files into

```
data/trajectories/<run_id>/
  manifest.json     # provenance: run_id, source ("selfplay-heuristic"), fork_commit, jar_sha256,
                    # anvil_commit, pool_version, obs_schema, seed_base, format, decks, created,
                    # games, decisions, raw/compressed bytes   (engine hash lives HERE, never in records)
  obs-0000.zst      # worker frame files, renumbered; frames untouched (ingest is a copy + index, not a re-encode)
  index.jsonl       # per game: file, offset, lengths, seed, record count, decks
  games.jsonl       # per-game outcome records (merged worker progress logs)
```

Reader API (`anvil.store.TrajectoryStore`): `store.game(i)` → header + decisions (with `ret` joined) + end; `store.iter_decisions(method=..., tags=...)` streaming across games. The corpus is regenerable; the store has no backup story by design.

**Tensor assembly** (`anvil.encoder.transform`, v0): deterministic, versioned transform from one `dec` record + game header + perspective → dense arrays (entity feature matrix + card-identity indices + count features after multiset dedup, global vector, per-player vectors). Vocabularies (zones, phases, counters — `mtg.` namespaced) live in a checked-in JSON, grown data-driven; unknown vocabulary entries are loud errors at transform time, not silent zeros. The full §1/§2 encoder (embeddings, fusion MLP) is D4; D1's transform is the boundary contract plus the leak test.

## Budget check (unchanged from the plan, now with shapes)

Midgame commander observation ≈ 40–80 logged entities × ~50–70 B + globals ≈ **2–6 KB raw** — the plan's band, with libraries-omitted doing the heavy lifting. ×1,136 callbacks/game (pool census mean) ≈ ~4 MB raw/game ≈ 2 TB raw at 500K games; consecutive-observation redundancy is extreme by construction (one entity flips per record, key strings repeat every line), which is what the 10–30× → **100–200 GB** target leans on. D3 measures; decision 7 lists the levers if it misses.

**First smoke measurement (2026-07-04, 5 pool games, single worker):** ~2 MB raw/game (in band), zstd-3 per-game frames compress **~70×** → **28 KB/game** — 500K games ≈ **~14 GB**, an order of magnitude inside the target. Serialization haircut ~4.3% single-worker (small sample; D3 is the real measurement). Same seeds with/without `-obs`: **bit-identical outcomes** — the serializer is a pure observer. *(True of the D1 build — the serializer alone. D2's option scan ends this; see the CastPlan section's measurements.)*

## Deliberately v2 (recorded so D3/D5 don't relitigate silently)

- Known-position library cards as promoted entities (scry/surveil-to-top); v1 logs the decisions, not the resulting library knowledge.
- Current-type residue beyond `pt` (type-changing effects that don't animate); continuous-effect child tokens (§2's non-reducible residue).
- State-stamp ref-dedup and keyframe+delta (decision 7 fallback levers).
- Construct-shaped `ret` serialization for combat (rung 2) — schema slot exists (`v` is shape-polymorphic), serializer doesn't.
