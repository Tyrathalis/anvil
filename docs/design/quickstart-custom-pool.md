# Quickstart: train Anvil on your own card pool

**Doc status:** reference · run the BC → self-play loop (and, optionally, the search) on your own Constructed pool, with the defaults that worked externally

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

**Formats: what works today.**

| You have | Status | How |
|---|---|---|
| 60-card Constructed decklists (a meta, a mirror, a cube's decks) | tested (Kryptic's single-deck mirror) | this page as written |
| 40-card decks (a Limited set) | accepted, untested | this page + `--main-size 40` (step 3); smoke 20 games first |
| Your own Commander decks | not documented yet | the project's own Commander pool is built from Duel Commander meta lists (the `dc` slot); a guide for bringing your own Commander pool, or any other format, is planned but not written |
| Multiplayer | not supported | — |

Two format names appear in the commands and mean different things. `--format Constructed` (the
harness, `final_read.py`, `selfplay.py`) is the Forge game type the engine plays. `--pool-format
pauper` / `--format pauper` (on `anvil.pool` and `anvil.encoder`) is the pool slot your decklists
live in. The Constructed slot is called `pauper` for historical reasons; it accepts any 60-card
decklists and does not check rarity.

## 0. Prerequisites

| Thing | Why |
|---|---|
| Linux or macOS, 16+ cores, 32+ GB RAM (everything below was measured on Linux) | Forge workers are the bottleneck: ~5 CPU-seconds per game, one JVM per worker at 2 GB heap. Nothing needs systemd or `/proc`; the run launcher (§7½) is plain Python |
| An NVIDIA GPU with ≥ 12 GB (a 4090 is what everything below was measured on) | the decision server and the learner; `--device cpu` exists on every driver but generation then waits on inference |
| JDK 17+ and Maven | building the Forge fork (Java 26 works; the fork compiles at release 17) |
| Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/) | the Anvil package |
| ~30 GB of disk | the fork, the Qwen3 embedding model (~8 GB), stores and checkpoints |
| A display, or `Xvfb` (Linux) | Forge initialises AWT before the CLI dispatches; with no `DISPLAY` the JVM exits 1 silently. The harness defaults `DISPLAY=:0`; on a headless Linux box run `Xvfb :0 &` first. macOS has a display; leave `DISPLAY` unset there |

Optional, for unattended runs: the [Claude Code CLI](https://claude.com/claude-code) installed and
logged in (`claude login`). With it on the path, the run launcher (§7½) answers its own alerts by
running a short read-only headless session that pushes to your phone and messages the Claude Code
session doing the work. Without it, the alert queue and a desktop toast are the coverage.

## 1. Build the Forge fork

Anvil runs on a fork of Forge with the bridge, the observation recorder and the search
machinery (`Tyrathalis/forge`, branch `master`). Upstream Forge will not work.

```bash
git clone --filter=blob:none https://github.com/Tyrathalis/forge.git
```

```bash
export FORGE_DIR=$PWD/forge
```

```bash
cd forge && mvn -P windows-linux -pl forge-gui-desktop -am package -DskipTests
```

The jar lands in `forge-gui-desktop/target/*-jar-with-dependencies.jar`. Anvil finds the fork
through `FORGE_DIR`. Keep it exported in every shell you run Anvil from; the fallback default,
`~/Everything/Projects/forge`, is the author's layout and will not match yours.
Every run manifest pins the jar's SHA-256 and the fork commit, so rebuilding the fork mid-run is
refused, not silently absorbed.

## 2. Install Anvil

```bash
git clone https://github.com/Tyrathalis/anvil.git && cd anvil && uv sync
```

Everything below runs from the Anvil checkout with `uv run`. Data lives under `data/` in the
checkout (gitignored).

## 3. Make the pool

A pool is a manifest (the card list + the decks, content-hashed into a pool version) plus the
`.dck` files installed into Forge's user deck store, which the workers resolve by name. Your
decklists go in the `pauper` slot (see *Formats* above).

**Decklists.** Drop your decklists into `data/pool/pauper/raw/decks/` as `<id>.txt` in MTGO export form
(`4 Lightning Bolt` per line, a blank line or `Sideboard` header before the sideboard, ≤ 15
sideboard cards, 4-of limit on non-basics), one file per deck, numeric ids. Every card name
must exist in the fork's `cardsfolder`; unresolved names exclude the deck and are reported.
Two decks is enough for a mirror; a Limited set wants dozens (draft them with Forge's own
draft AI or any drafter you trust, export, and drop them here).

**Build.** Snapshot the banlist, build, install. The build **drops every deck that contains a
card on the official Pauper banlist**, since the slot began as Pauper. If your lists are not Pauper,
skip the `banlist` command and write an empty snapshot instead; the build uses the newest-sorting
`banlist-*.json`:

```bash
mkdir -p data/pool/pauper/raw && echo '{"fetched": "custom", "cards": []}' > data/pool/pauper/raw/banlist-custom.json
```

Either way, check the build's report of excluded decks and their reasons before moving on.

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

**Embed.** Embed the pool's card text (once per pool; downloads `Qwen/Qwen3-Embedding-4B` the first time):

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
runs about 60 games/min, so 4,000 games is about an hour and 30,000 is an overnight — launch it
through the run launcher (§7½) rather than leaving a terminal open. `STOP` in the run dir pauses
it; `resume` picks up at game granularity.

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

### 7a. Optional: search as the behavior policy

The plain loop above is the proven path, and the one to run first. The search is this project's
current research line (M12): it can make the games the loop learns from better than the network
would play alone, at about 2.5× the time per game. On our pool a lookahead is worth about +2.5pp
to the network that uses it. Whether training on it makes the network *alone* stronger is what
our current runs are measuring. It has not been run outside this project yet, so start with a
20-game smoke.

**What it does.** At some of a seat's decision points, before choosing, the worker tries every
legal option on copies of the game and lets the network's value head judge where each one leads.
It is a one-step lookahead, not a tree search (not MCTS):

- **The option search.** At a searched window (the seat's own main phase, empty stack) every
  legal option is played out on a copy of the game. Each copy reshuffles the hidden cards the
  seat cannot see, so the search never uses information the player would not have. Play continues
  under the current policy until the seat's next such window, and the value head scores the
  position there. `-searchrolls` copies per option share their random draws, so options are
  compared on the same luck.
- **Acting.** The option the network would have played anyway (the *natural pick*) is always
  among those tried. If the best option beats it by at least the bar (`-searchact`, 0.10 in win
  probability), the seat plays an option sampled from the search's values (`-searchtemp`);
  otherwise it plays the natural pick.
- **The follow-up choice.** Many options lead straight into a second choice: a target, a mode,
  a tutor pick, an ordering. On the best few option paths (`-searchsurf`), the search also tries
  each answer to that first follow-up choice. The option is worth its best answer, and for the
  kinds in `-searchactkinds` the seat plays that answer too.
- **Choosing where to search.** Searching every window is expensive and most never change the
  pick. A small extra output of the network (the *allocation head*) predicts where the search
  would change the pick; only those windows are searched, plus a random 10% (`-searchfloor`)
  that keeps its training data honest. A checkpoint that has not trained the head yet (your BC
  checkpoint) searches every window until the loop has fit it.
- **What the network learns.** At a window where the search changed the pick, the training
  record is the search's choice: the policy is trained toward it, and the usual policy gradient
  runs on every window. The network you deploy plays alone. The search exists to make its
  training games better, and it never runs at play time.

**Words used below.** *Window*: a point where a seat is asked to choose. *Void*: an option the
copy could not play out (the engine refused it); it is skipped, not scored. *Surface*: one of the
follow-up choices above. *Leaf*: where a copy stops and the value head scores it.

**Turn it on** by adding `--search-recipe` to the §7 command, with our recipe:

```
--search-recipe "-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchsurfcap 8 -searchact 0.10 -searchtemp 0.025 -searchactkinds entity_one,entity_set,mode"
```

The driver adds the allocation head's flags itself (`-searchalloc <threshold> -searchfloor 0.1`,
the threshold re-derived each iteration from the serving checkpoint; `--search-alloc off` searches
at the uniform rate instead). It also records the search's rows into each iteration's store
(`search.jsonl`) and turns on the trainer's search terms (`--distill-frac` 0.05, `--alloc-frac`
0.02). `--jar <path>` pins one Forge jar for the whole run. Leaving out `-search` gives a game path
identical to the plain loop, byte for byte.

**How to tell whether it is helping.** With a recipe the loop's periodic arms read twice
(`--arms-lookahead on`, the default): the network alone and the network with the search. The
network-alone number is the one that matters. If with-lookahead climbs while network-alone stays
flat, the search is not teaching, and the extra 2.5× is wasted. Confirm with the §8 paired read,
which reads the network alone. `search_join.json` beside each iteration's checkpoint shows how
many windows were searched and acted on.

**The flags.** Every `-search*` flag is a flag of the Forge worker, passed through
`--search-recipe`.

| Flag | Default | What it does |
|---|---|---|
| `-search` | off | turn the search on for every model-played seat (`-searchseats <csv>` names seats; a heuristic seat named there is searched too, a control) |
| `-searchrate p` | 1.0 | search each candidate window with probability p (seeded) |
| `-searchrolls R` | 1 | copies per option, with shared random draws across options (2 in the recipe) |
| `-searchopts N` | 0 = all | cap on the options tried |
| `-searchmana` | off | also try pure mana abilities (58% of candidates when on, nearly all void) |
| `-searchleaf next\|eot\|h<N>\|end` | `next` | where a copy stops: the seat's next window (measured as the best judge) / end of turn / N turns later / the game's end (the actual result, no value head) |
| `-searchact bar` | off | the acting rule: act where the best option beats the natural pick by ≥ bar; absent = record only, never act |
| `-searchtemp T` | 0.025 | how sharply the acted option is sampled from the search's values (0 = always the best) |
| `-searchsurf B` | 0 | on the top-B option paths, also try each answer to the first follow-up choice (tutor / discard / mode / order / scry / damage / target) |
| `-searchsurfcap C` | 12 | answers tried per follow-up choice (8 in the recipe) |
| `-searchactkinds <csv\|all>` | none | follow-up kinds whose best answer the seat also plays (the recipe: `entity_one,entity_set,mode`); payments are never acted |
| `-searchalloc tau` | off | search only where the allocation head's P(the search would act) ≥ tau; off = the rate alone |
| `-searchfloor f` | 0.1 | the random share of windows searched regardless of the head |
| `-searchdeep B` | 0 | a second, deeper look (two turns, 4 copies) at the natural pick + top-B options when the first margin is close (in [`-searchdeeplo` 0.02, bar)); needs `-searchact`; ≈ 2.8× the time per game |
| `-searchpay B` / `-searchpayleaf` | 0 / `eot` | also try the ways to pay for the top-B options (recorded for study, never acted) |
| `-searchrollsalt <long>` | 0 | vary the copies' random draws between runs |
| `-searchclock s` | 900 | wall-clock allowance per searched game (raise it for `h<N>` / `end` leaves) |
| `-searchvoidskip 0\|1` | 1 | do not retry an option whose first copy voided |
| `-searchvoidrescue` | off | record-only: re-try a voided option with the heuristic's plan and record its value |

`uv run python -m anvil.store search-rows <run-dir>` backfills search rows into a store ingested
before that command existed. The design and the measurements behind all of this are the design doc
[§3e](anvil-design-v2.md#3e-search-as-the-behavior-policy-m12-adr-0101--adr-0118).

**The fleet (search runs).** One model server is one Python process and saturates at about twelve search workers.
Run `uv run python -m anvil.bridge.server --servers N ...` to start N servers on consecutive ports
and give the harness the matching list, `--bridge grpc:localhost:P,grpc:localhost:P+1,...`; chunks
are assigned round-robin. Pin N = ceil(workers / 12) and keep workers under your core count (24 on a
32-core box; 32 runs games 2.5× slower). The recipe of record on a 7950X + 4090 is 24 workers × 2
servers ≈ 300–350 games/hour searched; `selfplay.py` derives N from `--workers`. The servers print a
per-minute `[server] stats` occupancy line. A `YIELD` file in a run dir stops new chunks from
launching without asking workers to exit (a foreign GPU job does the same automatically), and the
load — workers × servers — is part of any search run's recipe: a paired read pins it on both arms.

## 7½. Running the long steps unattended

Steps 4, 7 and 8 take hours. Do not run them as foreground commands in a terminal you might
close, and do not hand-roll `nohup` wrappers: launch them through the run launcher, which is the
whole unattended-run checklist in one command (ADR-0107).

```bash
uv run python -m anvil.runs launch --name pauper-loop --dir data/training/pauper-loop --stall-min 60 -- \
  uv run python -m anvil.training.selfplay --name pauper-loop --ckpt data/training/bc-pauper/last.pt ... (the §7 command)
```

It detaches (the command survives your terminal and your session), unbuffers the child's output
into `<dir>/run.log`, runs it at low priority, records the run's state as it goes, and prints one
line naming what it armed:

```
[runs] LAUNCHED pauper-loop: state ~/.local/state/anvil/runs/pauper-loop.json (running, pid 41213), log .../run.log, stall alarm 60 min on data/training/pauper-loop, sinks queue+desk, check-in claude (self-test OK, 3 s)
```

While it runs, the launcher's supervisor watches the run's own directory: no new file for
`--stall-min` minutes raises a `stalled` alert, a fresh file after that raises `recovered`, and
the exit raises `done` or `failed` with the exit code and the last lines of the log. A run that
dies in its first ten seconds is a recorded failure, not a silent absence. The reads:

```bash
uv run python -m anvil.runs status            # every run: running / stalled / done / failed / gone
uv run python -m anvil.runs alerts --unacked  # what you have not seen yet
uv run python -m anvil.runs wait --name pauper-loop   # block a script until it ends (exit 0 = done)
uv run python -m anvil.runs ack --all
uv run python -m anvil.runs pause --name pauper-loop --wait   # STOP for the loop; records `paused`, no FAILED push
uv run python -m anvil.runs relaunch --name pauper-loop       # the same command again, in place; the loop resumes its state
```

For a maintenance reboot: `pause --wait`, update, reboot, `relaunch`. A run launched with
`--resume-on-gone` is relaunched by the sweep timer itself when its supervisor is found dead
(a reboot, an OOM kill), up to `--resume-max` times, so after the reboot your only step is the
login. A job that is idle on purpose (the harness yielding the GPU to another job, the learner
parked on a VRAM cotenant) writes `heartbeat.json` in the run dir so the stall alarm stays quiet.
`selfplay.py --wall-hours H` stops a loop between iterations once its accumulated box time
(summed across pauses) reaches H and runs the closing reads.

Alerts land in `~/.local/state/anvil/alerts.jsonl` and, as side effects, on a desktop toast
(`notify-send` on Linux, `osascript` on macOS). To reach your phone set `ANVIL_NOTIFY_CMD` to any
executable that takes `<title> <message>`; with [ntfy](https://ntfy.sh) that is a two-line script:

```bash
#!/bin/sh
curl -s -H "Title: $1" -d "$2" https://ntfy.sh/<your-topic> > /dev/null
```

**The LLM check-in.** With the Claude Code CLI installed and logged in (`claude login`), the
launcher's supervisor answers its own alerts: on `failed`, `stalled`, `gone` and a `done` after
more than an hour it runs a short headless `claude -p` session (read-only tools) that pushes one
notification to your phone, messages any Claude Code session on the machine whose title mentions
Anvil, and acks the alert. The launch runs a three-second self-test first and says so in the
coverage line (`check-in claude (self-test OK, 3 s)`); if the CLI is missing or its login has
expired the line says `check-in NONE — ...` and an alert records it, so you know at launch that
nobody will answer. `--checkin none` turns it off; `--watch 'data/runs/<name>-*'` adds artifact
roots to the stall check for a chain whose arms write outside its own dir.

If the machine reboots or the supervisor itself is killed, the run's state says `running` with a
dead pid; `uv run python -m anvil.runs sweep` marks it `gone`, alerts and checks in, and
`uv run python -m anvil.runs install-sweep` puts that on a systemd user timer every ten minutes
(a cron line elsewhere). [docs/ops/run-checkin.md](../ops/run-checkin.md) keeps the read-only
prompt as a fallback for a machine with the desktop app but no CLI. `--memory-max 20G` caps the
child through `systemd-run` on Linux and is ignored with a note elsewhere. `STOP` files still
work: the driver exits cleanly and the launcher records `done`.

## 8. Read the result

```bash
uv run python scripts/final_read.py --ckpt data/training/<name>-loop/iter-024/train/last.pt --name <name>-i24 --format Constructed --pool-format pauper --pairs-file data/runs/bc-corpus-<timestamp>/pairs.txt --games 1000 --workers 8 --skip-ante
```

Read every 5–10 iterations with this, not with the arms. Kryptic's mirror: 55.2% at iteration
25 (n = 1,000, ±1.6). Our pool: parity at iteration ~20 of the first recipe, 53.5% after the
drill work (on the current engine). Nobody on Forge has reported much past 55% against the heuristic with a network alone.

## 9. What it costs

| Stage | Wall (one 7950X + 4090) |
|---|---|
| 4,000 heuristic games at 16 workers | ~1 h |
| BC, 200K steps at batch 32 | ~2 h |
| 25 self-play iterations × 480 games | ~10–12 h |
| One 2,000-game paired read | ~1.5 h |
| 7a: the same loop under the search | ~2.5× the plain loop per game (24 workers × 2 servers) |

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
The search (7a): design doc [§3e](anvil-design-v2.md#3e-search-as-the-behavior-policy-m12-adr-0101--adr-0118).
The rules behind "read with 2,000 paired games, never per-round evals": [standing-rules.md](../standing-rules.md).
