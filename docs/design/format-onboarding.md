# Format onboarding — bringing a card pool or a format to Anvil

**Doc status:** living · what a "format" is in Anvil, which ones run today, and the checklist for adding one

*Written 2026-09-23. The [quickstart](quickstart-custom-pool.md) is the step-by-step run; this page
says which format settings to give it, and what it takes to add a format the pipeline does not know
yet. The research-grade section at the end is for results the project would compare or promote.*

## What "format" means here

A format touches four layers. Each has its own name in the commands, so it helps to keep them apart:

| Layer | What it decides | Where it is set |
|---|---|---|
| **Game type** | the rules the engine plays: starting life, command zone, mulligan | `--format` on the harness, `final_read.py` and `selfplay.py`: a Forge `GameType` name (`Commander`, `Constructed`) |
| **Pool slot** | the deck shape the build accepts, the banlist it applies, where the decks live | `--format` on `anvil.pool` / `anvil.encoder`, `--pool-format` everywhere else: `dc` or `pauper` today |
| **Model format row** | the format one-hot and scalars (start life, deck size, singleton, command zone, mulligan variant) the network reads | `anvil/encoder/vocab_mtg.json` (`formats`, `format_features`) + the `fmt_*` column in `GLOBAL_FEATURES` (`anvil/encoder/transform.py`) |
| **Research assets** | evalset pairs, the critic, calibration maps, reference numbers | per pool and per engine era (last section) |

The game type and the model row must agree. The Forge worker writes the game type into every game's
header, and the encoder rejects a game type it has no row for (`VocabError: unknown format`). It
never guesses.

## What runs today

| Format | Pool slot | Model row | Status |
|---|---|---|---|
| **1v1 Commander** (40 life, 100-card singleton, command zone) | `dc` | `Commander` | **works end to end**; the project's own pool |
| **Constructed** (60-card, or 40-card untested; sideboard) | `pauper` (the name is historical; any lists) | **missing** | **blocked on current main.** The pool pipeline works, but the model row was never added, so featurizing a Constructed game raises `VocabError` (since the M9 format one-hot, 2026-08-21). The fix is routed to the first worktree after the M12 shakedown (≈ 09-27); it is also this page's worked example below |
| Anything else Forge plays (Brawl, Oathbreaker, Limited as its own type, …) | none | none | needs a slot and a row (the checklist below) |
| Multiplayer | — | — | not supported: the bridge, the reads and the value head are 1v1 |

## Bringing your own decks in a supported format

Follow the [quickstart](quickstart-custom-pool.md) with these settings:

| | 1v1 Commander | Constructed (once unblocked) |
|---|---|---|
| `SLOT` (pool commands, `--pool-format`) | `dc` | `pauper` |
| `GAME` (`--format` on runs and reads) | `Commander` | `Constructed` |
| Pool directory | `data/pool/` (the `dc` slot predates the per-slot layout) | `data/pool/pauper/` |
| Decklist shape | 99 main + the commander (or a partner pair) in the sideboard section | 60 main (`--main-size 40` for Limited decks), ≤ 15 sideboard, 4-of limit |
| Banlist the build applies | the Duel Commander list (`duelcommander.com`) | the official Pauper list |
| Forge deck store | `~/.forge/decks/commander/` | `~/.forge/decks/constructed/` |

**The banlist.** `build` drops every deck containing a card on the slot's banlist: the Duel Commander
list for `dc`, the Pauper list for `pauper`. If that is not your format's list, skip the `banlist`
command and write an empty snapshot instead:
`echo '{"fetched": "custom", "cards": []}' > <pool dir>/raw/banlist-custom.json`. The build uses the
newest-sorting `banlist-*.json`, and `custom` sorts after the dated snapshots. Always read the
build's list of excluded decks and their reasons.

**One ingredient per deck the quickstart names:** each `<id>.txt` decklist needs a `<id>.json`
beside it. `{}` is enough; the fetcher fills event metadata there, and the build reads it only for
provenance.

## Adding a format

This part is code. Every item is small, but together they make a **dataset boundary** ([ADR-0018](../decisions/ADR-0018-ruleset-scope-clarification.md)):
record it in an ADR and never compare numbers across it.

1. **The model row.** Append the Forge game-type name to `formats` and its row to `format_features`
   in `anvil/encoder/vocab_mtg.json`, and a matching `fmt_<name>` column after the last `fmt_*`
   entry in `GLOBAL_FEATURES` (`anvil/encoder/transform.py`; `GLOBAL_SCALE` grows with it).
   `Vocab` refuses to load if the two lists disagree. **Watch the checkpoint loader:**
   `load_compat` (`anvil/policy/model.py`) zero-pads new global columns at the *end* of the
   globals, but since Build 4 the five format scalars follow the one-hot. A new one-hot column
   lands before them, so `load_compat` must insert the zeros at the one-hot's end instead;
   otherwise every old checkpoint reads its format scalars through the wrong weights. The test
   that proves it: a pre-change checkpoint's forward on a Commander game is byte-identical after
   the change, plus a round-trip featurize of a header with the new name.
2. **The pool slot** (skip it when an existing slot's deck shape and banlist fit, as Constructed
   formats fit `pauper`). Copy `anvil/pool/pauper/` to `anvil/pool/<slot>/`; change the deck-shape
   check in `decklist.py` and the banlist source in `fetch.py`; add the slot to
   `FORGE_DECKS_SUBDIR` in `anvil/pool/__init__.py` and to the `--format` / `--pool-format` choices
   in `anvil/pool/__main__.py`, the harness (`anvil/bridge/harness/__main__.py`),
   `anvil/training/selfplay.py` and `scripts/final_read.py`.
3. **The engine.** Nothing, if Forge has the game type: `AnvilRun -f <GameType>` plays it. The
   only Commander-specific branch in the fork is the commander-player constructor.
4. **Smoke.** Build a two-deck pool, run 20 heuristic games with `--obs`, ingest, and run 1,000 BC
   steps. Every layer is exercised before anything costs hours.

**Worked example: unblocking Constructed.** Step 1 only: `Constructed` with start life 20, deck
size 60, singleton 0, command zone 0, mulligan variant 1 (London), with the `load_compat` insert
fix and its identity test. The `pauper` slot already exists. Then the step 4 smoke, and the
quickstart's Constructed column is live again.

## Research-grade onboarding

To compare a format's numbers inside this project, or to promote a checkpoint on it, it also needs
the assets the Commander pool has:

- **A pool pin.** `<pool dir>/CURRENT` names the manifest every driver resolves; a new pool
  version is its own era.
- **A pairs file and a fixed population** for the paired read: the deck pairs and seeds both arms
  share, frozen before the first read ([ADR-0096](../decisions/ADR-0096-m10-closeout.md)).
- **A reference read**: the heuristic and the first checkpoint read on that population, so later
  gains have an anchor.
- **Ante certification** ([ADR-0014](../decisions/ADR-0014-ante-certification.md)): a full-visibility
  critic trained on the pool, certified on an identical-deck mirror, before luck-corrected reads
  are used. Until then every read is raw (`--skip-ante`).
- **Calibration maps** for any critic-derived number: isotonic maps are era-scoped
  ([ADR-0036](../decisions/ADR-0036-d3-critic-calibration.md)) and are re-fit, never carried over.
- **A `forkcheck` baseline** on the new game type, so later fork changes can prove they are
  behavior-identical there too ([ADR-0025](../decisions/ADR-0025-d4-rebase-closeout.md)).

Training one network on two formats at once is a separate, later question (the design doc's
multi-format bet, §2): the interface above exists so that it can be tried, not because it has been.
