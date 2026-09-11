#!/usr/bin/env bash
# M12 Build 3 evening 4 close (ADR-0105 addendum 09-10): THE h2 RELABEL — the
# payment pool re-labelled under the h2 leaf (the calibration read: the h2 leaf's
# positives convert at t 2.9 vs eot's 1.6, twice as many at the same bar), then
# the evening-4 chain on it: the pool read → pay_fit (the set-keyed head at
# pos-weight 8) → the build → the served-head smoke → the paired read (off = the
# pay tag withheld / on = the head at argmax) on the pinned jar.
#
# Two detached chains: the label run (build3_surface_labels.sh: the evening-4
# recipe with -searchpayleaf h2, rolls 2, rate 0.5, 16 workers, the clock 3,600 s) and the
# pay chain (build3_pay_chain.sh), which waits for the pool's DONE. Each
# registers with watchd and notifies. Usage: build3_h2_relabel.sh
#   env: GAMES (1000), WORKERS (16), SEED (20260910), ROLLS (2), RATE (0.5), CLOCK (3600),
#        POS_WEIGHT (8), MIN_ROLLS (2), PAY_BAR (0 = argmax), READ_GAMES (300)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
cd "$REPO"
GAMES=${GAMES:-1000}; WORKERS=${WORKERS:-16}; SEED=${SEED:-20260910}
POS_WEIGHT=${POS_WEIGHT:-8}; MIN_ROLLS=${MIN_ROLLS:-2}; PAY_BAR=${PAY_BAR:-0}; READ_GAMES=${READ_GAMES:-300}
# rolls 2 / rate 0.5 / clock 3,600 (the 21:50 restart): at rolls 4 / rate 1 the h2 copies — NETWORK-played
# for 2–3 turns on self-play, unlike the calibration's heuristic copies — saturated the single model
# server (110% CPU, the workers at 30% waiting on it, 29 g/h on 16 workers, 31% of games clipped at
# 2,400 s); 4× fewer asks keeps one server ahead of 16 workers and the games under the clock
ROLLS=${ROLLS:-2}; RATE=${RATE:-0.5}; CLOCK=${CLOCK:-3600}
POOL_OUT=$REPO/data/runs/build3-surface-labels4
CHAIN_OUT=data/runs/build3-e4h2
JAR=$REPO/data/runs/build3-paycal/forge-b3cal.jar   # the pin 287e8cca45 (the leaf family)
TAGS_NOPAY=mtg.priority,mtg.mulligan_keep,mtg.mulligan_tuck,mtg.trigger,mtg.binary,mtg.number,mtg.attack,mtg.block,mtg.surface.entity_one,mtg.surface.entity_set,mtg.surface.mode,mtg.surface.order,mtg.surface.damage
mkdir -p "$POOL_OUT" "$CHAIN_OUT"
echo "$(date -Iseconds) h2 relabel: pool=$POOL_OUT chain=$CHAIN_OUT jar=$JAR games=$GAMES workers=$WORKERS seed=$SEED rolls=$ROLLS rate=$RATE clock=$CLOCK posw=$POS_WEIGHT minrolls=$MIN_ROLLS paybar=$PAY_BAR" | tee -a "$CHAIN_OUT/relabel.log"

# 1. the label run (the e3 ckpt serving every tag but pay; the copies' pay slot under h2)
NAME=b3-surflab4 OUT="$POOL_OUT" GAMES="$GAMES" WORKERS="$WORKERS" SEED="$SEED" ROLLS="$ROLLS" RATE="$RATE" \
  PAY=2 PAYLEAF=h2 PAYTEL=1 TAGS="$TAGS_NOPAY" CLOCK="$CLOCK" JAR="$JAR" \
  setsid nohup bash scripts/build3_surface_labels.sh > "$POOL_OUT/run.out" 2>&1 < /dev/null &
echo "label run pid $!" | tee -a "$CHAIN_OUT/relabel.log"
sleep 5

# 2. the pay chain (waits for the pool's DONE; the set-keyed head at pos-weight 8; argmax serve)
POOL_OUT="$POOL_OUT" OUT="$CHAIN_OUT" CKPT_OUT=data/training/m12-build3-e4h JAR="$JAR" \
  POS_WEIGHT="$POS_WEIGHT" MIN_ROLLS="$MIN_ROLLS" PAY_BAR="$PAY_BAR" READ_GAMES="$READ_GAMES" ARMS="off on" READ_NAME=b3e4h \
  setsid nohup bash scripts/build3_pay_chain.sh > "$CHAIN_OUT/paychain.out" 2>&1 < /dev/null &
echo "pay chain pid $!" | tee -a "$CHAIN_OUT/relabel.log"
