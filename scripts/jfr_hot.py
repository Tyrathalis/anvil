"""JFR hot-frame read for an Anvil worker (the throughput week, 2026-09-14;
m12-plan record 09-09: "a JFR profile of one worker per regime").

    uv run python scripts/jfr_hot.py <rec.jfr | dir> [--top 40] [--md out.md]

Reads `jfr print --json --events jdk.ExecutionSample` (plus the exception
and GC summaries) and reports: the SELF top frames (top of stack), the
INCLUSIVE frames (any frame in the stack; the cost of a call tree), and the
bucket split the plan asks for — engine playout / heuristic AI / the search
directive / GameCopier / the obs snapshot + featurize / bridge / Anvil
controller / other — by the first matching frame from the top of the stack.
Exceptions thrown per class (an exception used as control flow is a cost).
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

BUCKETS = [
    ("game-copier", ("forge.game.GameCopier", "forge.game.card.CardCopyService")),
    ("obs-snapshot", ("forge.anvil.Obs", "forge.ai.anvil.Obs", "forge.anvil.Featur", "forge.ai.anvil.Featur",
                      "forge.ai.anvil.Snapshot", "forge.ai.anvil.AbilityKey")),
    ("bridge", ("forge.anvil.GrpcBridge", "io.grpc.", "io.netty.", "com.google.protobuf")),
    ("search-directive", ("forge.view.AnvilRun$SearchMonitor", "forge.ai.anvil.SearchDirective",
                          "forge.ai.anvil.Surfaces", "forge.ai.anvil.Census")),
    ("anvil-controller", ("forge.ai.anvil.", "forge.anvil.")),
    ("payment-enum", ("forge.ai.anvil.PaymentEnumerator",)),
    ("heuristic-ai", ("forge.ai.",)),
    ("engine", ("forge.game.", "forge.card.", "forge.util.", "forge.")),
    ("gc-or-jvm", ("java.", "jdk.", "sun.", "com.google.common.")),
]


def _bucket(frames: list[str]) -> str:
    # payment-enum is under forge.ai.anvil — test it before the controller bucket
    order = [b for b in BUCKETS if b[0] == "payment-enum"] + [b for b in BUCKETS if b[0] != "payment-enum"]
    for f in frames:
        for name, prefixes in order:
            if any(f.startswith(p) for p in prefixes):
                return name
    return "other"


def _frames(ev: dict) -> list[str]:
    st = ev.get("values", {}).get("stackTrace") or {}
    out = []
    for fr in st.get("frames", []):
        m = fr.get("method") or {}
        t = (m.get("type") or {}).get("name") or "?"
        out.append(f"{t}.{m.get('name', '?')}")
    return out


def load_samples(path: Path) -> list[list[str]]:
    js = subprocess.run(
        ["jfr", "print", "--json", "--events", "jdk.ExecutionSample", "--stack-depth", "64", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(js)
    return [_frames(ev) for ev in data.get("recording", {}).get("events", [])]


SCAFFOLD = ("forge/game/phase/PhaseHandler.", "forge/game/GameAction.startGame", "forge/game/Match.startGame",
            "forge/view/AnvilRun", "forge/view/TimeLimitedCodeBlock", "forge.view.", "forge/game/GameAction.checkStateEffects",
            "forge/game/GameAction.checkStaticAbilities", "forge/game/GameAction.checkGameOverCondition")
SUSPECTS = ("GameActionUtil.getAlternativeCosts", "StaticAbilityAlternativeCost", "Card.getAllPossibleAbilities",
            "GameAction.checkStaticAbilities", "GameAction.checkStateEffects", "ReplacementHandler.getReplacementList",
            "ReplacementHandler.run", "TriggerHandler.runTrigger", "TriggerHandler.runWaitingTriggers",
            "StaticAbilityContinuous", "CardProperty.cardHasProperty", "CardLists.getValidCards", "CardLists.filter",
            "ComputerUtilMana.canPayManaCost", "ComputerUtilMana.payManaCost", "ComputerUtilCost.canPayCost",
            "ComputerUtilCombat", "AiController.chooseSpellAbilityToPlay", "AiController.getSpellAbilities",
            "PaymentEnumerator", "AnvilOptions", "GameCopier", "CardCopyService", "Obs.", "Snapshot", "AbilityKey",
            "GrpcBridge", "PlayerControllerAnvil", "SearchMonitor.doSearch", "SearchMonitor.playCopy",
            "Card.getState", "Card.updateStateForView", "TrackableObject", "Zone.isCardAddedThisTurn",
            "Combat.", "CardView", "GameView", "Thread.getStackTrace", "AnvilOptions.withScratchRng")


def _first_forge(frames: list[str]) -> str:
    for f in frames:
        if f.startswith("forge") and "Throwable" not in f:
            return f
    return frames[0] if frames else "?"


def load_exceptions(path: Path) -> collections.Counter:
    js = subprocess.run(
        ["jfr", "print", "--json", "--events", "jdk.JavaExceptionThrow", "--stack-depth", "16", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    c: collections.Counter = collections.Counter()
    for ev in json.loads(js).get("recording", {}).get("events", []):
        v = ev.get("values", {})
        cls = ((v.get("thrownClass") or {}).get("name")) or "?"
        fr = _frames(ev)
        c[(cls, _first_forge(fr))] += 1
    return c


def summarize(path: Path, top: int = 40) -> str:
    files = sorted(path.glob("*.jfr")) if path.is_dir() else [path]
    samples: list[list[str]] = []
    exc: collections.Counter = collections.Counter()
    for f in files:
        samples += load_samples(f)
        exc += load_exceptions(f)
    n = len(samples)
    self_c = collections.Counter(s[0] for s in samples if s)
    incl_c: collections.Counter = collections.Counter()
    for s in samples:
        for fr in set(s):
            incl_c[fr] += 1
    buckets = collections.Counter(_bucket(s) for s in samples)
    lines = [f"# JFR hot frames — {', '.join(f.name for f in files)}", "",
             f"{n} execution samples ({len(files)} file(s))", "", "## Buckets (first matching frame from the top)", "",
             "| bucket | samples | share |", "|---|---|---|"]
    for b, k in buckets.most_common():
        lines.append(f"| {b} | {k} | {k / n:.1%} |")
    lines += ["", f"## Self top {top} (top of stack)", "", "| frame | samples | share |", "|---|---|---|"]
    for fr, k in self_c.most_common(top):
        lines.append(f"| `{fr}` | {k} | {k / n:.1%} |")
    lines += ["", f"## Inclusive top {top} — forge frames, scaffolding removed", "",
              "| frame | samples | share |", "|---|---|---|"]
    shown = 0
    for fr, k in incl_c.most_common():
        if not fr.startswith("forge") or fr.startswith(SCAFFOLD):
            continue
        lines.append(f"| `{fr}` | {k} | {k / n:.1%} |")
        shown += 1
        if shown >= top:
            break
    lines += ["", "## Suspects (inclusive; the plan's list + the upstream PR 11916 frames)", "",
              "| frame contains | samples | share |", "|---|---|---|"]
    for sus in SUSPECTS:
        k = sum(1 for s in samples if any(sus in fr for fr in s))
        if k:
            lines.append(f"| `{sus}` | {k} | {k / n:.1%} |")
    tot_exc = sum(exc.values())
    lines += ["", f"## Exceptions thrown: {tot_exc}", "", "| class | thrown at | count |", "|---|---|---|"]
    for (cls, fr), k in exc.most_common(15):
        lines.append(f"| `{cls}` | `{fr}` | {k} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--md", default=None)
    a = ap.parse_args()
    md = summarize(Path(a.path), a.top)
    if a.md:
        Path(a.md).write_text(md)
        print(f"[jfr_hot] -> {a.md}")
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
