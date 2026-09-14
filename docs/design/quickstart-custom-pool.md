# Quickstart: train Anvil on your own card pool

**Doc status:** reference · run the BC → self-play loop on an arbitrary small Constructed pool, with the defaults that worked externally

**Who this is for:** you have a set of 60-card decklists (a Limited set, a cube, a single-deck
mirror, a small Constructed meta) and want a pilot that plays them at Forge-heuristic strength or
better, on one consumer box, in a few days. This is the path Kryptic ran in September 2026 on a
single-deck mirror (BC 38.9% → self-play 55.2% vs the heuristic in under a day of training;
[devlog](../devlog/2026-09-07-session2.md)). Everything else in this repo assumes the 1v1
Commander pool; this page is the Constructed exception.

**What you get:** a checkpoint that plays your decks through Forge's own AI controller, a paired
winrate read against the Forge heuristic, and a trajectory store of every game (observations,
decisions, outcomes) you can mine for card statistics.

**What you do not get (yet):** human-like play (there is no human game corpus), Limited-shaped
formats beyond "40-card decks under the Constructed rules" (untested; see step 3), multiplayer,
and luck-corrected reads (those need a value critic trained on your pool; the raw paired read is
what you use).

## 0. Prerequisites

| Thing | Why |
|---|---|
| Linux, 16+ cores, 32+ GB RAM | Forge workers are the bottleneck: ~5 CPU-seconds per game, one JVM per worker at 2 GB heap |
| An NVIDIA GPU with ≥ 12 GB (a 4090 is what everything below was measured on) | the decision server and the learner; `--device cpu` exists on every driver but generation then waits on inference |
| JDK 17+ and Maven | building the Forge fork (Java 26 works; the fork compiles at release 17) |
| Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/) | the Anvil package |
| ~30 GB of disk | the fork, the Qwen3 embedding model (~8 GB), stores and checkpoints |
| A display, or `Xvfb` | Forge initialises AWT before the CLI dispatches; with no `DISPLAY` the JVM exits 1 silently. The harness defaults `DISPLAY=:0`; on a headless box run `Xvfb :0 &` first |

## 1. Build the Forge fork

Anvil runs on a fork of Forge with the bridge, the observation recorder and the search
machinery (`Tyrathalis/forge`, branch `master`). Upstream Forge will not work.

```bash
git clone --filter=blob:none https://github.com/Tyrathalis/forge.git
```

```bash
cd forge && mvn -P windows-linux -pl forge-gui-desktop -am package -DskipTests
```

The jar lands in `forge-gui-desktop/target/*-jar-with-dependencies.jar`. Anvil finds the fork
through `FORGE_DIR` (default `~/Everything/Projects/forge`); export it if you cloned elsewhere.
Every run manifest pins the jar's SHA-256 and the fork commit, so rebuilding the fork mid-run is
refused, not silently absorbed.

## 2. Install Anvil

```bash
git clone https://github.com/Tyrathalis/anvil.git && cd anvil && uv sync
```

```bash
export FORGE_DIR=/path/to/forge
```

Everything below runs from the Anvil checkout with `uv run`. Data lives under `data/` in the
checkout (gitignored).

## 3. Make the pool

A pool is a manifest (the card list + the decks, content-hashed into a pool version) plus the
`.dck` files installed into Forge's user deck store, which the workers resolve by name. The
Constructed pipeline lives in the slot named `pauper` for historical reasons; it accepts any
60-card decklists and does not check rarity.

1. Drop your decklists into `data/pool/pauper/raw/decks/` as `<id>.txt` in MTGO export form
   (`4 Lightning Bolt` per line, a blank line or `Sideboard` header before the sideboard, ≤ 15
   sideboard cards, 4-of limit on non-basics), one file per deck, numeric ids. Every card name
   must exist in the fork's `cardsfolder`; unresolved names exclude the deck and are reported.
   Two decks is enough for a mirror; a Limited set wants dozens (draft them with Forge's own
   draft AI or any drafter you trust, export, and drop them here).
2. Snapshot the banlist, build, install:

```bash
uv run python -m anvil.pool --format pauper banlist
```

```bash
uv run python -m anvil.pool --format pauper build
```

```bash
uv run python -m anvil.pool --format pauper install
```

`build` writes `data/pool/pauper/pool-<version>.json`, the `.dck` files, and the `CURRENT` pin
every driver resolves; `install` copies the decks into `~/.forge/decks/constructed/`. The
harness hash-checks the installed decks against the built ones on every launch, so a stray edit
in the Forge GUI cannot silently change your data.

**40-card decks:** pass `--main-size 40` to `build`. The engine is then handed 40-card decks under
`GameType.Constructed`. This path is untested here; the parser and the manifest accept it, and
nothing downstream keys on deck size, but a first run should be a 20-game smoke.

3. Embed the pool's card text (once per pool; downloads `Qwen/Qwen3-Embedding-4B` the first time):

```bash
uv run python -m anvil.encoder embed --model qwen3 --format pauper
```

This writes `data/embeddings/<pool_version>-qwen3.safetensors`. The pool version is the
`ACTIVE` line of `uv run python -m anvil.pool --format pauper status`.

## 4. Generate the imitation corpus

Heuristic-vs-heuristic games with every decision recorded. `--bridge-seats 2` names a seat that
does not exist, so neither seat bridges and both play the stock Forge AI while the observation
log still captures every callback and the heuristic's answer.

```bash
uv run python -m anvil.bridge.harness launch --pool --pool-format pauper --format Constructed --games 4000 --games-per-pair 5 --workers 8 --bridge-seats 2 --obs --census --purpose bc-corpus --seed-base 20260901
```

The run lands in `data/runs/bc-corpus-<timestamp>/`. Sizes that worked: 4,000 games for a
mirror (Kryptic); 50,000–110,000 for a 1,700-card pool (ours). At 16 workers the heuristic mirror
runs about 60 games/min, so 4,000 games is about an hour and 30,000 is an overnight. `STOP` in
the run dir pauses it; `resume` picks up at game granularity.

Ingest the run into a trajectory store:

```bash
uv run python -m anvil.store ingest data/runs/bc-corpus-<timestamp> --verify
```

It prints the store path under `data/trajectories/`.

## 5. Behavior-clone the heuristic

```bash
uv run python -m anvil.training.train --store data/trajectories/<store> --embed data/embeddings/<pool_version>-qwen3 --pool-manifest data/pool/pauper/pool-<pool_version>.json --batch 32 --lr 3e-4 --warmup 500 --steps 200000 --pass-weight 0.1 --out data/training/bc-<name>
```

Those are Kryptic's settings on 4,000 games. On a larger corpus raise `--batch` toward 256 (the
default; a 24 GB card shared with a desktop OOMs at 512) and drop `--steps` toward one epoch.
The checkpoint is `data/training/bc-<name>/last.pt`; it carries the embedding and manifest
paths, so every later driver finds the pool through it.

## 6. Read it against the heuristic

The paired read: both seat assignments, argmax serve, the same seeds for both seats. A pairs file
is a tab-separated list of deck-name pairs; the corpus run wrote one you can reuse:

```bash
uv run python scripts/final_read.py --ckpt data/training/bc-<name>/last.pt --name bc-<name> --format Constructed --pool-format pauper --pairs-file data/runs/bc-corpus-<timestamp>/pairs.txt --games 1000 --workers 8 --skip-ante
```

2,000 games total gives ±1.1pp. Expect 35–47% at this point; that is where every
imitation-on-Forge pipeline lands, and it is the floor the loop climbs from. `--skip-ante` is
required: the luck correction needs a full-visibility critic trained on your pool.

## 7. Self-play

```bash
uv run python -m anvil.training.selfplay --name <name>-loop --ckpt data/training/bc-<name>/last.pt --iterations 25 --games 480 --seed-base 20260902 --format Constructed --pool-format pauper --heur-frac 0.5 --reask --penalty 0.01 --penalty-grouping first --chunk 10 --guard-veto-mult 4.0 --lr 1e-5 --rl-seg 64 --traj-per-step 4 --epochs 1 --arms-every 5 --arms-pairs data/runs/bc-corpus-<timestamp>/pairs.txt
```

What the flags mean, in the order you would change them:

- **`--iterations 25 --games 480`**: 480 games per iteration, half mirror, half vs the heuristic
  (`--heur-frac 0.5`). On a 4090 one iteration is ~25 minutes (generation ~1,400 s, training
  ~300 s), so 25 iterations is a night.
- **`--reask`**: when the engine vetoes a chosen spell (unpayable, no legal target) the seat is
  re-asked with that option removed instead of passing. Keep it on.
- **`--penalty 0.01 --penalty-grouping first`**: the small cost on vetoed attempts that keeps the
  veto rate from drifting; `--guard-veto-mult 4.0` halts the run if it drifts 4× anyway.
- **`--arms-every 5`**: a 200-game read vs the heuristic every 5 iterations, per seat. It is a
  trend instrument (±2.5pp); do not quote it.
- **`--rl-seg 64`** bounds learner memory; raise it on a bigger card.

Checkpoints land in `data/training/<name>-loop/iter-NNN/train/last.pt`; the monitor is
`monitor.jsonl` in the loop dir (reward, entropy, KL, veto rate per iteration). `STOP` in the loop
dir exits cleanly after the current iteration.

## 8. Read the result

```bash
uv run python scripts/final_read.py --ckpt data/training/<name>-loop/iter-024/train/last.pt --name <name>-i24 --format Constructed --pool-format pauper --pairs-file data/runs/bc-corpus-<timestamp>/pairs.txt --games 1000 --workers 8 --skip-ante
```

Read every 5–10 iterations with this, not with the arms. Kryptic's mirror: 55.2% at iteration
25 (n = 1,000, ±1.6). Our pool: parity at iteration ~20 of the first recipe, 52.8% after the
drill work. Nobody on Forge has reported much past 55% against the heuristic with a network alone.

## 9. What it costs

| Stage | Wall (one 7950X + 4090) |
|---|---|
| 4,000 heuristic games at 16 workers | ~1 h |
| BC, 200K steps at batch 32 | ~2 h |
| 25 self-play iterations × 480 games | ~10–12 h |
| One 2,000-game paired read | ~1.5 h |

## Troubleshooting

- **`no forge jar under $FORGE_DIR/forge-gui-desktop/target`**: build the fork (step 1) or export
  `FORGE_DIR`.
- **Workers exit 1 with empty logs**: no display. `Xvfb :0 &` and `export DISPLAY=:0`.
- **`N pool cards have no cardsfolder script (pool/fork mismatch?)`**: a deck names a card the
  fork does not script, or `FORGE_DIR` points at a different Forge. Fix the decklist or the path.
- **`installed pool decks differ from data/pool/decks`**: re-run `install`; something edited the
  Forge deck store.
- **Learner OOM**: lower `--batch` (BC) or `--rl-seg` (self-play).
- **The veto guard halts the loop**: read `monitor.jsonl`; a veto rate climbing past 4× iteration
  0 usually means the penalty is too small for your pool. Restart from the last good iteration
  with `--penalty 0.02`.

## Where the numbers come from

Throughput and corpus sizes: [ADR-0003](../decisions/ADR-0003-m0-closeout.md),
[ADR-0009](../decisions/ADR-0009-m1-closeout.md). The loop recipe: [d6-vtrace-loop.md](d6-vtrace-loop.md),
[ADR-0026](../decisions/ADR-0026-m3-closeout.md). The external replication: [devlog 2026-09-07](../devlog/2026-09-07-session2.md).
The rules behind "read with 2,000 paired games, never per-round evals": [standing-rules.md](../standing-rules.md).
