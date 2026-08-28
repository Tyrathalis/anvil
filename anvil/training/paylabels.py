"""M10 R5: ADR-0075 supervised conditional payment labels as direct aux
(m10-plan supervised-conditional wiring, adjudicated 2026-08-26; the M7
seqlabels-join wire shape on the banked observe frames).

**This deliberately reverses the M9 "no BC-from-heuristic" pin** (the
`dataset.py` TASKS comment): that pin kept HEURISTIC answers out of
training — auto-answered windows are exactly where the heuristic is least
trustworthy. These labels are the opposite provenance: ENGINE-CERTIFIED
outcome classes (h2 rollout certification, ADR-0075/ADR-0082), the only
training signal the pay head receives while the PG staged mask holds.

Labels are ERA-ASSETS: certification is policy-conditional under
`d6-run11/iter-019` rollouts — the graft IS that ckpt, so the era weight is
1.0 at birth; the batch records its cert lineage so a future era can weight
or re-mint (the sweep machinery is the re-runnable label mint).

The loss is class-CE: −log Σ_cls p(choice) over the certified
outcome-equivalence class (ADR-0082 — exact-index CE would train the
arbitrary max-index tiebreak; 23/56 v2 positives are multi-arm classes).
Auto-correct rows carry cls=[0]. The ratesweep-descended
`payment-holdout-v1` is NEVER ingested here — it is the generalization
readout (m10-build-spec §5 family 5).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def build_pay_batch(
    evalset_dir: str,
    observe_jobs: str,
    observe_certout: str,
    obs_paths: list[str],
    feat,
    seg: int = 64,
) -> "dict | None":
    """Certified drills + banked observe frames -> collated segments with a
    per-row class mask. Joins on (batch, orig_job); retired drills (absent
    from the v2 evalset) drop out of the join. Returns None when nothing
    joins (callers must treat that as pay-labels-off and say so)."""
    from payment_drill_score import _observe_frames

    from anvil.training.dataset import collate

    ev = Path(evalset_dir)
    want: dict[tuple, dict] = {}
    for fname, kind in (("positive-drills.jsonl", "positive"),
                        ("autocorrect-drills.jsonl", "auto_correct")):
        for line in open(ev / fname):
            d = json.loads(line)
            cls = d.get("cls") if kind == "positive" else [0]
            want[(d["batch"], d["job"])] = {"cls": cls or [d["best"]], "kind": kind,
                                            "shape": d.get("shape")}

    cert: dict[int, dict] = {}
    for line in open(observe_certout):
        r = json.loads(line)
        if r.get("ev") == "certify" and r.get("arm") == 0:
            cert[r["job"]] = r
    frames = _observe_frames([str(p) for p in obs_paths])

    exs, classes, kinds = [], [], []
    miss = mismatch = 0
    for j in map(json.loads, open(observe_jobs)):
        lab = want.get((j["batch"], j["orig_job"]))
        if lab is None:
            continue  # retired or held rows: not in the join, by design
        c, f = cert.get(j["job"]), frames.get(j["job"])
        if c is None or f is None or not c.get("fired") or c.get("exec") != "observed":
            miss += 1
            continue
        header, w = f
        if len(w["opts"]) != j["exp_options"] + 1:
            mismatch += 1  # the ADR-0067 jar-drift class, excluded loudly
            continue
        ex, _aux = feat.example(w, header, "pay_class")
        if max(lab["cls"]) >= ex["cand_rows"].shape[0]:
            mismatch += 1
            continue
        exs.append(ex)
        classes.append(lab["cls"])
        kinds.append(lab["kind"])
    if not exs:
        return None

    segs = []
    for i in range(0, len(exs), seg):
        chunk = collate(exs[i : i + seg])
        b, cw = chunk["cand_mask"].shape
        cls_mask = torch.zeros(b, cw, dtype=torch.bool)
        for r, cls in enumerate(classes[i : i + seg]):
            for a in cls:
                cls_mask[r, a] = True
        chunk["pay_cls_mask"] = cls_mask
        chunk["pay_is_pos"] = torch.tensor(
            [k == "positive" for k in kinds[i : i + seg]]
        )
        segs.append(chunk)
    n_pos = sum(k == "positive" for k in kinds)
    return {
        "segs": segs,
        "n": len(exs),
        "n_pos": n_pos,
        "n_auto": len(exs) - n_pos,
        "miss": miss,
        "option_mismatch": mismatch,
        "evalset": str(evalset_dir),
    }


def pay_pass(
    net,
    pay_segs: list,
    forward_segments,
    w_pay: float,
    grad: bool = True,
) -> tuple[float, float, float]:
    """One pass over the pay-label batch: class-CE on the pay pointer head
    (−log Σ_cls p). Means over the whole batch; grad=True backwards the
    weighted total (the seq_pass contract). Returns (raw class-CE,
    positive-rows CE, auto-rows CE) — the per-kind split is the ADR-0069
    discrimination discipline (never blend the two in a readout)."""
    n_total = sum(next(iter(s.values())).shape[0] for s in pay_segs)
    tot = tot_pos = tot_auto = 0.0
    n_pos = sum(int(s["pay_is_pos"].sum()) for s in pay_segs) or 1
    n_auto = max(n_total - n_pos, 1)
    for seg, fwd in forward_segments(net, pay_segs, grad=grad):
        lp = fwd["policy_logits"].float().log_softmax(1)
        in_cls = lp.masked_fill(~seg["pay_cls_mask"], -1e9).logsumexp(1)
        ce_rows = -in_cls  # log_softmax already normalizes over valid cands
        l_pay = ce_rows.sum() / n_total
        if grad:
            (w_pay * l_pay).backward()
        tot += float(l_pay.detach())
        pos = seg["pay_is_pos"]
        tot_pos += float(ce_rows[pos].detach().sum()) / n_pos
        tot_auto += float(ce_rows[~pos].detach().sum()) / n_auto
    return tot, tot_pos, tot_auto
