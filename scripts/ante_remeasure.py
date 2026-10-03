"""The Ante re-measure summary (ADR-0119 step 2 / ADR-0121 §4; 10-03).

Reads the two seat arms of one final_read (its `read.done`: s0,s1 run dirs), the
certify reports final_read wrote with the standing full-vis critic
(data/runs/ante-<arm>.json) and the head-as-critic reports the chain wrote
(<out>/ante-head-<arm>.json), and prints one markdown read:

- per critic x arm: raw and fitted-beta corrected winrate, corr(raw, ledger),
  the variance ratio with its CI90, the effective-sample multiplier;
- per critic, the two arms POOLED into one 2,000-game ledger (the s1 arm's
  seats flipped so seat 0 is the test seat throughout) -- the number read
  against the pre-registered 1.5x bar (ADR-0119 step 3: corrected becomes the
  number of record; step 4: the amortized head is gated in);
- the draw-coverage census: draws corrected, draw_poisoned, shuffle_cleanse,
  against the 09-16 stake (9,930 corrected vs 10,735 poisoned; ADR-0121).

Usage: uv run python scripts/ante_remeasure.py --read-done <out>/read.done --out-dir <out> \
           --critic-name d4-critic-fullvis --head-ckpt <ckpt>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from anvil.ante.certify import aggregate, load_ledgers

BAR = 1.5
STAKE = "the 09-16 read: 9,930 draws corrected vs 10,735 skipped as poisoned (ADR-0121)"


def _flip(L: dict) -> dict:
    L = dict(L)
    L["winner"] = 1 - L["winner"]
    L["nodes"] = [{**r, "p": 1 - r["p"]} for r in L["nodes"]]
    return L


def _row(label: str, r: dict) -> str:
    cls = r.get("classes", {})
    sk = r.get("skips", {})
    return (
        f"| {label} | {r['games']} | {r['raw_winrate']:.4f} ± {r['raw_se']:.4f} | "
        f"{r['corrected_cv_winrate']:.4f} ± {r['corrected_cv_se']:.4f} | {r['corr_raw_lsum']:.3f} | "
        f"{r['var_ratio_cv']:.4f} {r['var_ratio_cv_ci90']} | **{r['effective_sample_multiplier']:.3f}** | "
        f"{cls.get('draw', {}).get('n_nodes', '—')} | {sk.get('draw_poisoned', 0)} | {sk.get('shuffle_cleanse', 0)} |"
    )


HEADER = (
    "| critic / arm | games | raw | corrected (fitted β) | corr(raw, ledger) | var ratio (CI90) | "
    "effective samples × | draws corrected | draw_poisoned | shuffle_cleanse |\n"
    "|---|---|---|---|---|---|---|---|---|---|"
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--read-done", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--critic-name", default="d4-critic-fullvis")
    ap.add_argument("--head-ckpt", default=None)
    ap.add_argument("--runs-dir", default="data/runs")
    a = ap.parse_args()
    out = Path(a.out_dir)
    arms = [Path(p.strip()) for p in Path(a.read_done).read_text().split(",") if p.strip()]
    critics = {a.critic_name: [Path(a.runs_dir) / f"ante-{d.name}.json" for d in arms]}
    if a.head_ckpt:
        critics[f"the head itself ({a.head_ckpt}, omniscient windows)"] = [
            out / f"ante-head-{d.name}.json" for d in arms
        ]

    print("# The Ante re-measure (ADR-0119 step 2): the ledger under two critics on the shuffle-mark jar\n")
    print(f"Arms: {', '.join(d.name for d in arms)} (s0 = the test seat on seat 0, s1 on seat 1). Stake: {STAKE}.\n")
    print(HEADER)
    pooled: dict[str, dict] = {}
    for cname, reps in critics.items():
        ledgers: list[dict] = []
        skips: dict[str, int] = {}
        for d, rep in zip(arms, reps):
            if not rep.exists():
                print(f"| {cname} / {d.name} | pending ({rep}) |")
                continue
            r = json.loads(rep.read_text())
            print(_row(f"{cname} / {d.name}", r))
            for k, v in r.get("skips", {}).items():
                skips[k] = skips.get(k, 0) + v
            L, _ = load_ledgers(Path(f"{rep}.ledger.jsonl"))
            ledgers.extend([_flip(x) for x in L] if "-s1-" in d.name else L)
        if ledgers:
            agg = aggregate(ledgers)
            agg["skips"] = skips
            pooled[cname] = agg
            print(_row(f"**{cname} / pooled**", agg))

    print("\n**Against the pre-registered 1.5× bar (ADR-0119 step 3):**\n")
    for cname, agg in pooled.items():
        m = agg["effective_sample_multiplier"]
        verdict = "CLEARS — corrected reads become the number of record; the amortized head is gated IN" if m >= BAR else "BELOW — the raw read stays of record, the ledger stays an audit"
        print(f"- {cname}: effective samples ×{m:.3f} (var ratio {agg['var_ratio_cv']:.4f}, CI90 {agg['var_ratio_cv_ci90']}; "
              f"corr(raw, ledger) {agg['corr_raw_lsum']:.3f}; ledger mean {agg['ledger_mean']:.5f} ± {agg['ledger_se']:.5f}, t {agg['ledger_t']}): **{verdict}**")
    print("\nDraw coverage reads from the census columns: a shuffle_cleanse row is a seat whose library knowledge the ledger "
          "voided on a mark; draws corrected rise by what the cleanse returned from the poisoned half.")


if __name__ == "__main__":
    main()
