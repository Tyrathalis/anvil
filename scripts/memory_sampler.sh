#!/usr/bin/env bash
# MEMORY SAMPLER for a running loop (10-17, after the second systemd-oomd kill of the big run at a training step —
# the run's own scope at 58 GB resident + 47 GB swapped): every INTERVAL seconds, one JSON line with the box's
# free/swap and the RSS + swap + count of each process class in the run (java workers, the model servers, the
# learner rl.py and its DataLoader workers, the loop driver) so the next OOM — or its absence — has a profile.
# Usage: bash scripts/memory_sampler.sh <out.jsonl> [interval_s=60]   (run detached; stop with kill)
set -u
OUT=$1; INTERVAL=${2:-60}
while true; do
  python3 - "$OUT" <<'PY'
import os,sys,time,json,re,glob
def meminfo():
    d={}
    for l in open('/proc/meminfo'):
        k,v=l.split(':'); d[k]=int(v.split()[0])//1024
    return d
classes={'java':0,'server':0,'rl':0,'rl_worker':0,'loop':0,'harness':0,'other_py':0}
rss={k:0 for k in classes}; swp={k:0 for k in classes}; cnt={k:0 for k in classes}
for p in glob.glob('/proc/[0-9]*'):
    try:
        cmd=open(p+'/cmdline','rb').read().replace(b'\0',b' ').decode(errors='replace')
        st=open(p+'/status').read()
    except Exception: continue
    if not cmd.strip(): continue
    m=re.search(r'VmRSS:\s+(\d+)',st); s=re.search(r'VmSwap:\s+(\d+)',st)
    r=int(m.group(1))//1024 if m else 0; w=int(s.group(1))//1024 if s else 0
    if 'java' in cmd.split()[0] or 'AnvilRun' in cmd: k='java'
    elif 'anvil.bridge.server' in cmd: k='server'
    elif 'anvil.training.rl' in cmd or '/rl.py' in cmd: k='rl'
    elif 'multiprocessing' in cmd and ('forkserver' in cmd or 'spawn' in cmd or 'resource_tracker' in cmd): k='rl_worker'
    elif 'anvil.training.selfplay' in cmd: k='loop'
    elif 'anvil.bridge.harness' in cmd: k='harness'
    elif 'python' in cmd.split()[0] and 'Anvil/.venv' in cmd: k='other_py'
    else: continue
    rss[k]+=r; swp[k]+=w; cnt[k]+=1
mi=meminfo()
row={'ts':time.strftime('%Y-%m-%dT%H:%M:%S'),'used_mb':mi['MemTotal']-mi['MemAvailable'],'avail_mb':mi['MemAvailable'],
     'swap_used_mb':mi['SwapTotal']-mi['SwapFree'],'rss_mb':rss,'swap_mb':swp,'count':cnt}
open(sys.argv[1],'a').write(json.dumps(row)+'\n')
PY
  sleep "$INTERVAL"
done
