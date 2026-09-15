"""JFR hot-frame read for an Anvil worker (the throughput week, 2026-09-14;
m12-plan record 09-09: "a JFR profile of one worker per regime").

    uv run python scripts/jfr_hot.py <rec.jfr | dir> [--top 40] [--md out.md] [--callers FRAME ...]

STREAMING: `jfr print` (text) is consumed event by event from a pipe and
only counters are kept — the first version loaded `jfr print --json` of a
77K-sample recording into one JSON string twice over while 24 recording
JVMs were live and OOM-killed the box (09-14 17:58). Never hold a
recording's samples in memory; a 16-game recording is ~16 MB on disk and
~1 GB as parsed JSON.

Reports: the bucket split the plan asks for — engine playout / heuristic
AI / the search directive / GameCopier / the obs snapshot + featurize /
bridge / Anvil controller — by the first matching frame from the top of
the stack; SELF top frames; INCLUSIVE forge frames (scaffolding removed);
the suspects table (the plan's list + the upstream PR 11916 frames); the
nearest callers of named frames; GC pauses; exceptions by thrower.
"""

from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path

BUCKETS = [
    ("payment-enum", ("forge.ai.anvil.PaymentEnumerator",)),
    ("game-copier", ("forge.ai.simulation.GameCopier", "forge.game.card.CardCopyService")),
    ("obs-snapshot", ("forge.ai.anvil.Obs", "forge.ai.anvil.Featur", "forge.ai.anvil.Snapshot", "forge.ai.anvil.AbilityKey")),
    ("bridge", ("forge.anvil.GrpcBridge", "io.grpc.", "io.netty.", "com.google.protobuf")),
    ("search-directive", ("forge.view.AnvilRun$SearchMonitor", "forge.ai.anvil.SearchDirective",
                          "forge.ai.anvil.Surfaces", "forge.ai.anvil.Census")),
    ("anvil-controller", ("forge.ai.anvil.", "forge.anvil.")),
    ("heuristic-ai", ("forge.ai.",)),
    ("engine", ("forge.game.", "forge.card.", "forge.util.", "forge.")),
    ("gc-or-jvm", ("java.", "jdk.", "sun.", "com.google.common.")),
]
SCAFFOLD = ("forge.game.phase.PhaseHandler.", "forge.game.GameAction.startGame", "forge.game.Match.startGame",
            "forge.view.", "forge.game.GameAction.checkStateEffects", "forge.game.GameAction.checkStaticAbilities",
            "forge.game.GameAction.checkGameOverCondition")
SUSPECTS = ("GameActionUtil.getAlternativeCosts", "StaticAbilityAlternativeCost", "Card.getAllPossibleAbilities",
            "GameAction.checkStaticAbilities", "GameAction.checkStateEffects", "ReplacementHandler.getReplacementList",
            "ReplacementHandler.run", "TriggerHandler.runTrigger", "TriggerHandler.runWaitingTriggers",
            "StaticAbilityContinuous", "CardProperty.cardHasProperty", "CardLists.getValidCards", "CardLists.filter",
            "ComputerUtilMana.canPayManaCost", "ComputerUtilMana.payManaCost", "ComputerUtilMana.getSourcesForShards",
            "ComputerUtilMana.groupSourcesByManaColor", "ComputerUtilCost.canPayCost", "ComputerUtilCombat",
            "ComputerUtilAbility.getSpellAbilities", "PaymentEnumerator", "AnvilOptions.priorityOptions",
            "AnvilOptions.payable", "AnvilOptions.withScratchRng", "GameCopier", "CardCopyService", "CardFactory.getCard",
            "Obs.", "Snapshot", "AbilityKey", "GrpcBridge", "PlayerControllerAnvil", "SearchMonitor.doSearch",
            "Card.updateStateForView", "TrackableObject", "CardView", "Combat.", "FCollection.addAll",
            "Thread.getStackTrace")

# `jfr print` text: an event block "jdk.ExecutionSample {" ... "stackTrace = [" frame lines "]" "}"
FRAME_RE = re.compile(r"^\s*([\w$.<>/]+)\.([\w$<>]+)\(")


class Agg:
    def __init__(self, callers: list[str]):
        self.n = 0
        self.self_c: collections.Counter = collections.Counter()
        self.incl_c: collections.Counter = collections.Counter()
        self.buckets: collections.Counter = collections.Counter()
        self.suspects: collections.Counter = collections.Counter()
        self.callers = callers
        self.caller_c: dict[str, collections.Counter] = {c: collections.Counter() for c in callers}
        self.caller_hits: collections.Counter = collections.Counter()

    def add(self, frames: list[str]) -> None:
        if not frames:
            return
        self.n += 1
        self.self_c[frames[0]] += 1
        for fr in set(frames):
            self.incl_c[fr] += 1
        self.buckets[_bucket(frames)] += 1
        for sus in SUSPECTS:
            if any(sus in fr for fr in frames):
                self.suspects[sus] += 1
        for target in self.callers:
            for i, fr in enumerate(frames):
                if target in fr:
                    self.caller_hits[target] += 1
                    j = i + 1
                    while j < len(frames) and target in frames[j]:
                        j += 1
                    self.caller_c[target][frames[j] if j < len(frames) else "?"] += 1
                    break


def _bucket(frames: list[str]) -> str:
    """The first frame from the top that names a forge/anvil bucket; JDK and
    guava frames (collections, iterators) are attributed to their caller —
    only a stack with no forge frame at all lands in gc-or-jvm."""
    jvm = False
    for f in frames:
        for name, prefixes in BUCKETS:
            if any(f.startswith(p) for p in prefixes):
                if name == "gc-or-jvm":
                    jvm = True
                    break
                return name
    return "gc-or-jvm" if jvm else "other"


def stream_samples(path: Path, agg: Agg) -> None:
    """One `jfr print` process per file; frames parsed line by line."""
    proc = subprocess.Popen(
        ["jfr", "print", "--events", "jdk.ExecutionSample", "--stack-depth", "64", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1 << 16,
    )
    frames: list[str] = []
    in_stack = False
    assert proc.stdout is not None
    for line in proc.stdout:
        if "stackTrace = [" in line:
            in_stack = True
            frames = []
            continue
        if in_stack:
            if line.strip().startswith("]"):
                in_stack = False
                agg.add(frames)
                frames = []
                continue
            m = FRAME_RE.match(line)
            if m:
                frames.append(f"{m.group(1)}.{m.group(2)}")
    proc.wait()


def stream_exceptions(path: Path) -> collections.Counter:
    proc = subprocess.Popen(
        ["jfr", "print", "--events", "jdk.JavaExceptionThrow", "--stack-depth", "16", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1 << 16,
    )
    c: collections.Counter = collections.Counter()
    cls = "?"
    first_forge = None
    in_stack = False
    assert proc.stdout is not None
    for line in proc.stdout:
        s = line.strip()
        if s.startswith("thrownClass = "):
            cls = s.split("=", 1)[1].strip().split(" ")[0]
            first_forge = None
        elif "stackTrace = [" in line:
            in_stack = True
        elif in_stack:
            if s.startswith("]"):
                in_stack = False
                c[(cls, first_forge or "?")] += 1
            elif first_forge is None:
                m = FRAME_RE.match(line)
                if m and m.group(1).startswith("forge") and "Throwable" not in m.group(1):
                    first_forge = f"{m.group(1)}.{m.group(2)}"
    proc.wait()
    return c


def gc_summary(path: Path) -> tuple[int, float]:
    """(collections, total pause seconds) from `jfr summary`-free parsing of jdk.GarbageCollection."""
    proc = subprocess.Popen(
        ["jfr", "print", "--events", "jdk.GarbageCollection", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1 << 16,
    )
    n, pause = 0, 0.0
    assert proc.stdout is not None
    for line in proc.stdout:
        s = line.strip()
        if s.startswith("sumOfPauses = "):
            n += 1
            pause += _seconds(s.split("=", 1)[1].strip())
    proc.wait()
    return n, pause


def _seconds(v: str) -> float:
    v = v.strip()
    for unit, k in (("ms", 1e-3), ("us", 1e-6), ("ns", 1e-9), ("s", 1.0), ("min", 60.0)):
        if v.endswith(unit):
            try:
                return float(v[: -len(unit)].strip()) * k
            except ValueError:
                return 0.0
    return 0.0


def summarize(path: Path, top: int = 40, callers: list[str] | None = None) -> str:
    files = sorted(path.glob("*.jfr")) if path.is_dir() else [path]
    agg = Agg(callers or [])
    exc: collections.Counter = collections.Counter()
    gcs, gc_s = 0, 0.0
    for f in files:
        stream_samples(f, agg)
        exc += stream_exceptions(f)
        g = gc_summary(f)
        gcs += g[0]
        gc_s += g[1]
    n = max(agg.n, 1)
    lines = [f"# JFR hot frames — {len(files)} file(s): {', '.join(f.name for f in files[:3])}{' …' if len(files) > 3 else ''}", "",
             f"{agg.n} execution samples; GC: {gcs} collections, {gc_s:.1f} s of pauses "
             f"(vs ≈ {agg.n * 0.02:.0f} s of sampled Java CPU at the 20 ms profile interval)", "",
             "## Buckets (first matching frame from the top)", "", "| bucket | samples | share |", "|---|---|---|"]
    for b, k in agg.buckets.most_common():
        lines.append(f"| {b} | {k} | {k / n:.1%} |")
    lines += ["", f"## Self top {top} (top of stack)", "", "| frame | samples | share |", "|---|---|---|"]
    for fr, k in agg.self_c.most_common(top):
        lines.append(f"| `{fr}` | {k} | {k / n:.1%} |")
    lines += ["", f"## Inclusive top {top} — forge frames, scaffolding removed", "", "| frame | samples | share |", "|---|---|---|"]
    shown = 0
    for fr, k in agg.incl_c.most_common():
        if not fr.startswith("forge") or fr.startswith(SCAFFOLD) or "$$Lambda" in fr or ".lambda$" in fr:
            continue
        lines.append(f"| `{fr}` | {k} | {k / n:.1%} |")
        shown += 1
        if shown >= top:
            break
    lines += ["", "## Suspects (inclusive; the plan's list + the upstream PR 11916 frames)", "",
              "| frame contains | samples | share |", "|---|---|---|"]
    for sus in SUSPECTS:
        k = agg.suspects.get(sus, 0)
        if k:
            lines.append(f"| `{sus}` | {k} | {k / n:.1%} |")
    for target in agg.callers:
        hit = agg.caller_hits.get(target, 0)
        lines += ["", f"## Callers of `{target}` ({hit} samples)", "", "| caller | samples | share of hits |", "|---|---|---|"]
        for fr, k in agg.caller_c[target].most_common(12):
            lines.append(f"| `{fr}` | {k} | {k / max(hit, 1):.1%} |")
    tot_exc = sum(exc.values())
    lines += ["", f"## Exceptions thrown: {tot_exc}", "", "| class | thrown at | count |", "|---|---|---|"]
    for (cls, fr), k in exc.most_common(12):
        lines.append(f"| `{cls}` | `{fr}` | {k} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--md", default=None)
    ap.add_argument("--callers", action="append", default=None, help="frame substring: table its nearest callers")
    a = ap.parse_args()
    md = summarize(Path(a.path), a.top, a.callers)
    if a.md:
        Path(a.md).write_text(md)
        print(f"[jfr_hot] -> {a.md}")
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
