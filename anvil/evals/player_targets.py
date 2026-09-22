"""Player-target audit (09-21, ADR-0116): on priority answers with a player target,
how often a seat targets ITSELF vs the opponent — the model's seats vs the heuristic's,
by registered seat. The 46%/11% read on b4post found the target decoder's mixed label."""

from __future__ import annotations

import collections
import glob
import json

import zstandard


def refs_of(plan: dict):
    for r in plan.get("tgt") or []:
        yield r
    for s in plan.get("sub") or []:
        for r in s.get("tgt") or []:
            yield r
    for m in plan.get("modes") or []:
        yield from refs_of(m)


def audit(dirs: list[str]) -> dict:
    c = collections.Counter()
    for d in dirs:
        for f in sorted(glob.glob(f"{d}/workers/inv-*/obs.zst")):
            with open(f, "rb") as fh:
                r = zstandard.ZstdDecompressor().stream_reader(fh)
                buf = b""
                pend: dict[int, tuple[int, str]] = {}
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    buf += chunk
                    lines = buf.split(b"\n")
                    buf = lines.pop()
                    for l in lines:
                        if not l.strip():
                            continue
                        rec = json.loads(l)
                        k = rec.get("k")
                        if k == "game":
                            pend = {}
                        elif k == "dec" and rec.get("m") == "chooseSpellAbilityToPlay":
                            pend[rec["s"]] = (int(rec["p"]), "model" if rec.get("by") == "bridge" else "heur")
                        elif k == "ret" and rec.get("s") in pend:
                            p, who = pend.pop(rec["s"])
                            v = rec.get("v")
                            if not isinstance(v, list):
                                continue
                            for plan in v:
                                if not isinstance(plan, dict):
                                    continue
                                c[(who, p, "casts")] += 1
                                for ref in refs_of(plan):
                                    if "pi" in ref:
                                        c[(who, p, "self" if int(ref["pi"]) == p else "opp")] += 1
    out = {}
    for who in ("model", "heur"):
        for p in (0, 1):
            s, o, n = c[(who, p, "self")], c[(who, p, "opp")], c[(who, p, "casts")]
            out[f"{who}_seat{p}"] = {"casts": n, "player_targets": s + o, "self": s, "opp": o,
                                     "self_rate": round(s / max(s + o, 1), 4)}
    return out



def battery_lines(dirs: list[str]) -> tuple[list[str], list[str]]:
    """(section lines, anomalies) for the run battery: the model's self-target
    rate vs the heuristic's in the same games; an anomaly when the model's is
    over twice the heuristic's on >= 100 player-targeted casts."""
    r = audit(dirs)
    m_s = r["model_seat0"]["self"] + r["model_seat1"]["self"]
    m_n = r["model_seat0"]["player_targets"] + r["model_seat1"]["player_targets"]
    h_s = r["heur_seat0"]["self"] + r["heur_seat1"]["self"]
    h_n = r["heur_seat0"]["player_targets"] + r["heur_seat1"]["player_targets"]
    m_r, h_r = m_s / max(m_n, 1), h_s / max(h_n, 1)
    lines = [
        "## Player targets (ADR-0116)",
        "",
        f"- model: {m_n} player-targeted casts, self-target rate {m_r:.3f} "
        f"(seat 0 {r['model_seat0']['self_rate']:.3f} / seat 1 {r['model_seat1']['self_rate']:.3f})",
        f"- heuristic: {h_n} player-targeted casts, self-target rate {h_r:.3f}",
        "",
    ]
    anomalies = []
    if m_n >= 100 and h_n >= 100 and m_r > 2 * h_r:
        anomalies.append(
            f"model self-target rate {m_r:.3f} > 2x the heuristic's {h_r:.3f} on {m_n} player-targeted "
            f"casts — the target decoder's player positions (ADR-0116 class)"
        )
    return lines, anomalies
