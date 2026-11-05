# The ComfyUI idle-unload timer — the box's other GPU tenant unloads itself after ten quiet minutes

**Doc status:** ACTIVE since 2026-11-04 — the user timer `comfyui-idle-unload.timer` is enabled on the box; the script and units live outside the repo (`~/.local/bin/comfyui-idle-unload`, `~/.config/systemd/user/comfyui-idle-unload.{service,timer}`) and this page is their copy of record.

## Why

ComfyUI keeps its last model loaded after a job: 17–19 GB of VRAM at 0% SM and a 21–23 GB host-RAM offload, for as long as the daemon lives. The harness's GPU yield rule holds any foreign process with ≥ 1,024 MB of VRAM as foreign (it cannot know when the next job arrives, and the training step cannot fit beside 17 GB on the 24 GB card), so a loaded-idle ComfyUI costs the big run the whole idle span: 2.2 h of generation inside iteration 378 on 11-04, of which the job itself was a fraction. The host offload is the standing hazard behind the host-memory wait (the learner's 33–35 GB beside 23 GB on a 62 GB box).

In use and loaded-idle are distinguishable from ComfyUI's own API (`GET /prompt` → `exec_info.queue_remaining`; `GET /queue`; `GET /history`), and ComfyUI has the unload verb the front end's "Unload Models" button uses: `POST /free {"unload_models": true, "free_memory": true}`. The worker unloads every model, resets its output cache and runs gc; `set_flag` notifies the queue's condition, so an idle worker acts at once (verified 11-04 17:42: the cache re-creation logged within the second).

## What runs

A oneshot service on a one-minute timer. Busy = a job running or pending, a new history head since the last poll (a job that finished between polls), or the daemon's SM share ≥ 5%. Idle ≥ `COMFY_IDLE_S` (600) while the daemon's VRAM ≥ `COMFY_VRAM_MB` (2,048) → `POST /free`, then a before/after line (VRAM and RSS) to the journal. Down or unreachable daemon → exit 0 silently. State in `$XDG_RUNTIME_DIR/comfyui-idle-unload.json`.

```bash
journalctl --user -u comfyui-idle-unload.service --since today
```

```bash
systemctl --user list-timers comfyui-idle-unload.timer
```

The cost: the first job after a quiet spell reloads its model from disk (tens of seconds). The verification still owed: the RSS line on the first real firing (a loaded model unloading), which the script logs by itself.

## The units

`~/.config/systemd/user/comfyui-idle-unload.service`:

```ini
[Unit]
Description=Unload ComfyUI's models after ten idle minutes (frees VRAM and the host-RAM offload)
After=comfyui.service

[Service]
Type=oneshot
ExecStart=%h/.local/bin/comfyui-idle-unload
Environment=COMFY_URL=http://100.106.120.33:8188
Environment=COMFY_IDLE_S=600
Environment=COMFY_VRAM_MB=2048
```

`~/.config/systemd/user/comfyui-idle-unload.timer`:

```ini
[Unit]
Description=Poll ComfyUI once a minute for the idle-unload

[Timer]
OnBootSec=3min
OnUnitActiveSec=60s
AccuracySec=10s
Unit=comfyui-idle-unload.service

[Install]
WantedBy=timers.target
```

The script is `~/.local/bin/comfyui-idle-unload` (Python 3, stdlib only); its copy of record is [scripts/comfyui_idle_unload.py](../../scripts/comfyui_idle_unload.py).
