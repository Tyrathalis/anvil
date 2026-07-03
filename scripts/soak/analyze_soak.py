#!/usr/bin/env python3
"""Summarize a soak-test run directory produced by run_soak.sh.

Usage: analyze_soak.py <out_dir>

Reports: games completed and games/hour, RSS start/end/max and trend (MB/h),
heap-after-GC trend (the actual leak signal), and full-GC count.
Stdlib only.
"""
import re
import sys
from pathlib import Path


def linear_slope(xs, ys):
    """Least-squares slope of ys over xs."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def main(out_dir: Path) -> None:
    print(f"=== Soak summary: {out_dir} ===")
    meta = out_dir / "meta.txt"
    if meta.exists():
        print(meta.read_text().strip())
    print()

    # RSS + game progress (ts_epoch, rss_kb, games_done)
    rss_csv = out_dir / "rss.csv"
    if rss_csv.exists():
        rows = []
        for line in rss_csv.read_text().splitlines():
            parts = line.split(",")
            if len(parts) >= 2 and parts[0].isdigit():
                ts = int(parts[0])
                kb = int(parts[1]) if parts[1].isdigit() else None
                games = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
                if kb is not None:
                    rows.append((ts, kb, games))
        if rows:
            t0 = rows[0][0]
            hours = (rows[-1][0] - t0) / 3600
            rss_mb = [kb / 1024 for _, kb, _ in rows]
            slope = linear_slope([(t - t0) / 3600 for t, _, _ in rows], rss_mb)
            print(f"duration: {hours:.2f} h ({len(rows)} samples)")
            print(f"RSS MB: start {rss_mb[0]:.0f}, end {rss_mb[-1]:.0f}, "
                  f"max {max(rss_mb):.0f}, trend {slope:+.1f} MB/h")
            games = [g for _, _, g in rows if g is not None]
            if games and hours > 0:
                print(f"games: {games[-1]} completed, {games[-1] / hours:.0f} games/h "
                      f"({3600 / (games[-1] / hours):.1f} s/game)" if games[-1] else "games: 0")
    else:
        print("no rss.csv found")
    print()

    # GC log: after-GC heap sizes, e.g. "... 512M->128M(4096M) 12.345ms"
    gc_log = out_dir / "gc.log"
    if gc_log.exists():
        pat = re.compile(r"\[([\d.]+)s\].*GC\(\d+\).*?(\d+)M->(\d+)M\((\d+)M\)")
        after, times = [], []
        full_gcs = 0
        with gc_log.open() as f:
            for line in f:
                if "Pause Full" in line:
                    full_gcs += 1
                m = pat.search(line)
                if m:
                    times.append(float(m.group(1)) / 3600)
                    after.append(int(m.group(3)))
        if after:
            slope = linear_slope(times, after)
            q = len(after) // 4 or 1
            print(f"GC events parsed: {len(after)}, full GCs: {full_gcs}")
            print(f"heap-after-GC MB: first-quartile avg {sum(after[:q]) / q:.0f}, "
                  f"last-quartile avg {sum(after[-q:]) / q:.0f}, trend {slope:+.1f} MB/h")
            print("verdict hint: flat heap-after-GC + flat RSS = no leak; "
                  "climbing heap-after-GC = LearnForge-style leak lives.")
        else:
            print("gc.log present but no heap transitions parsed")
    else:
        print("no gc.log found")

    # Anomalies in sim output
    sim_log = out_dir / "sim.log"
    if sim_log.exists():
        text = sim_log.read_text(errors="replace")
        for marker in ("OutOfMemoryError", "Exception", "Stopping slow match as draw"):
            n = text.count(marker)
            if n:
                print(f"sim.log: {n}x {marker!r}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
