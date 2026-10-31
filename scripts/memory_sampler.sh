#!/usr/bin/env bash
# MEMORY SAMPLER + WATCHDOG for a running loop (10-17, after the second systemd-oomd kill of the big run at a
# training step — the run's own scope at 58 GB resident + 47 GB swapped; the learner's DataLoader workers ≈ 7 GB
# apiece of decode state, see the 10-17 devlog). Every INTERVAL seconds, one JSON line with the box's free/swap and
# the RSS + swap + count of each process class in the run (java workers, the model servers, the learner rl.py and its
# forkserver DataLoader workers, the loop driver, the harness), plus the box's cotenants: `comfy` (a resident ComfyUI,
# the one GPU cotenant that has run beside the big run; 10-31) and `other` (every other process with a command line —
# the desktop, the browser, kopia, the app — so the unattributed share is a named number, not a gap).
#
# THE WATCHDOG (user, 10-17): when MemAvailable stays under AVAIL_MIN_MB for TRIP_SAMPLES consecutive samples WHILE a
# learner is up, it terminates the learner and its whole forkserver tree together (rl.py, the forkserver, every
# pt_data_worker, the resource tracker — a learner killed alone leaves its workers alive at full size, the 10-17
# orphans) before the box swaps into oomd's 90% line. The iteration's training step fails cleanly (the stores and the
# checkpoint are on disk; the loop records the failure, the chain exits FAILED, a relaunch reruns the step); the
# trip is recorded in the sample line and in <out dir>/WATCHDOG-TRIP. The chain's retry at a smaller RL_WORKERS on a
# trip is the second half, landed at an iteration boundary (bash reads a running script incrementally).
# Usage: bash scripts/memory_sampler.sh <out.jsonl> [interval_s=20]
#   env: WATCHDOG (1 = armed; default 1), AVAIL_MIN_MB (2048), TRIP_SAMPLES (2), WATCHDOG_DRY (1 = log, never kill)
# Run as a user unit so it outlives the session:
#   systemd-run --user --unit=anvil-memsampler -p MemoryMax=500M -p WorkingDirectory=$PWD /usr/bin/bash $PWD/scripts/memory_sampler.sh $PWD/data/runs/big-run/memory.jsonl 20
set -u
OUT=$1; INTERVAL=${2:-20}
export WATCHDOG=${WATCHDOG:-1} AVAIL_MIN_MB=${AVAIL_MIN_MB:-2048} TRIP_SAMPLES=${TRIP_SAMPLES:-2} WATCHDOG_DRY=${WATCHDOG_DRY:-0}
STATE=/tmp/anvil-memsampler.$$.low; echo 0 > "$STATE"
while true; do
  python3 - "$OUT" "$STATE" <<'PY'
import os,sys,time,json,re,glob,signal
out,state=sys.argv[1],sys.argv[2]
def meminfo():
    d={}
    for l in open('/proc/meminfo'):
        k,v=l.split(':'); d[k]=int(v.split()[0])//1024
    return d
classes=('java','server','rl','rl_worker','loop','harness','other_py','comfy','other')
rss={k:0 for k in classes}; swp={k:0 for k in classes}; cnt={k:0 for k in classes}; pids={k:[] for k in classes}
for p in glob.glob('/proc/[0-9]*'):
    try:
        cmd=open(p+'/cmdline','rb').read().replace(b'\0',b' ').decode(errors='replace')
        st=open(p+'/status').read()
    except Exception: continue
    if not cmd.strip(): continue
    m=re.search(r'VmRSS:\s+(\d+)',st); s=re.search(r'VmSwap:\s+(\d+)',st)
    r=int(m.group(1))//1024 if m else 0; w=int(s.group(1))//1024 if s else 0
    a0=cmd.split()[0]
    if 'java' in a0 or 'AnvilRun' in cmd: k='java'
    elif 'anvil.bridge.server' in cmd: k='server'
    elif 'anvil.training.rl' in cmd or '/rl.py' in cmd: k='rl'
    elif 'Anvil/.venv' in a0 and 'multiprocessing' in cmd and ('forkserver' in cmd or 'spawn' in cmd or 'resource_tracker' in cmd): k='rl_worker'
    elif 'anvil.training.selfplay' in cmd: k='loop'
    elif 'anvil.bridge.harness' in cmd: k='harness'
    elif 'python' in a0 and 'Anvil/.venv' in a0: k='other_py'
    elif 'ComfyUI' in cmd: k='comfy'
    else: k='other'
    rss[k]+=r; swp[k]+=w; cnt[k]+=1; pids[k].append(int(p.split('/')[-1]))
mi=meminfo(); avail=mi['MemAvailable']
row={'ts':time.strftime('%Y-%m-%dT%H:%M:%S'),'used_mb':mi['MemTotal']-avail,'avail_mb':avail,
     'swap_used_mb':mi['SwapTotal']-mi['SwapFree'],'rss_mb':rss,'swap_mb':swp,'count':cnt}
# ---- the watchdog ----
armed=os.environ.get('WATCHDOG','1')=='1'; dry=os.environ.get('WATCHDOG_DRY','0')=='1'
amin=int(os.environ.get('AVAIL_MIN_MB','2048')); need=int(os.environ.get('TRIP_SAMPLES','2'))
learner_up=cnt['rl']>0
low=int(open(state).read() or 0)
low=low+1 if (avail<amin and learner_up) else 0
open(state,'w').write(str(low))
if armed and low>=need:
    # the learner tree: rl.py + the forkserver tree (pt_data_worker children carry the forkserver cmdline). Descend
    # from every rl pid by ppid so nothing of the tree survives (the 10-17 orphans).
    tree=set(pids['rl'])|set(pids['rl_worker'])
    changed=True
    while changed:
        changed=False
        for p in glob.glob('/proc/[0-9]*'):
            try: st=open(p+'/status').read()
            except Exception: continue
            pp=re.search(r'PPid:\s+(\d+)',st); pid=int(p.split('/')[-1])
            if pp and int(pp.group(1)) in tree and pid not in tree: tree.add(pid); changed=True
    row['watchdog']={'trip':True,'dry':dry,'avail_mb':avail,'low_samples':low,'killed':sorted(tree)}
    if not dry:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for pid in tree:
                try: os.kill(pid, sig)
                except ProcessLookupError: pass
            time.sleep(5)
            alive=[pid for pid in tree if os.path.exists(f'/proc/{pid}')]
            if not alive: break
        row['watchdog']['alive_after']=alive
    open(os.path.join(os.path.dirname(out),'WATCHDOG-TRIP'),'a').write(json.dumps(row)+'\n')
    open(state,'w').write('0')
open(out,'a').write(json.dumps(row)+'\n')
PY
  sleep "$INTERVAL"
done
