"""
Score predicted points against labelled ones.

    python score.py labels/ predictions.csv
    python score.py labels/ predictions.csv --tol 4

`labels/` holds the JSON files the labeller saves. `predictions.csv` has rows of
`image,x,y[,class]`, the same format build.py takes for seeds, so a detector's
output can be fed to both.

Detections are matched to labels one-to-one, closest first, within `--tol`
pixels. The pairing is greedy over a global distance ordering rather than
per-detection nearest, because the latter lets two detections claim the same
label and reports a miss and a false positive that are really one duplicate.

Only numpy is needed beyond the standard library.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def match(pred, true, tol):
    pairs = sorted(((abs(px - tx) ** 2 + abs(py - ty) ** 2) ** 0.5, i, j)
                   for i, (px, py, _) in enumerate(pred)
                   for j, (tx, ty, _) in enumerate(true)
                   if abs(px - tx) <= tol and abs(py - ty) <= tol)
    used_p, used_t, out = set(), set(), []
    for d, i, j in pairs:
        if d > tol or i in used_p or j in used_t:
            continue
        used_p.add(i); used_t.add(j); out.append((i, j, d))
    return out


def load_predictions(path: Path):
    per = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            per[os.path.basename(r["image"])].append(
                (float(r["x"]), float(r["y"]), (r.get("class") or "").strip() or None))
    return per


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("labels", type=Path, help="folder of .json files from the labeller")
    ap.add_argument("predictions", type=Path, help="CSV of image,x,y[,class]")
    ap.add_argument("--tol", type=float, default=5.0,
                    help="pixels within which a prediction counts as a hit (default: 5)")
    args = ap.parse_args()

    preds = load_predictions(args.predictions)
    files = sorted(args.labels.glob("*.json"))
    if not files:
        raise SystemExit(f"no .json label files in {args.labels}")

    tot_tp = tot_fp = tot_fn = 0
    cls_n = cls_ok = 0
    confusion: Counter = Counter()
    errs: list[float] = []

    print(f"{'image':34s} {'labels':>7s} {'pred':>6s} {'P':>6s} {'R':>6s} "
          f"{'F1':>6s} {'err':>7s}  swept")
    for f in files:
        lab = json.loads(f.read_text(encoding="utf-8"))
        name = lab.get("image", f.stem)
        true = [(p["x"], p["y"], p.get("cls")) for p in lab.get("points", [])]
        pred = preds.get(name, preds.get(f.stem, []))
        m = match(pred, true, args.tol)

        tp = len(m); fp = len(pred) - tp; fn = len(true) - tp
        tot_tp += tp; tot_fp += fp; tot_fn += fn
        p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        errs += [d for _i, _j, d in m]

        for i, j, _d in m:
            want = true[j][2]
            if not want:
                continue
            cls_n += 1
            if pred[i][2] == want:
                cls_ok += 1
            else:
                confusion[(want, pred[i][2] or "none")] += 1

        sw = f"{lab.get('tiles_reviewed', '?')}/{lab.get('tiles_total', '?')}"
        e = np.median([d for _i, _j, d in m]) if m else float("nan")
        print(f"{name[:32]:34s} {len(true):7d} {len(pred):6d} {p:6.2f} {r:6.2f} "
              f"{f1:6.2f} {e:6.2f}px  {sw}")

    P = tot_tp / max(tot_tp + tot_fp, 1)
    R = tot_tp / max(tot_tp + tot_fn, 1)
    print("\n" + "=" * 74)
    print(f"POOLED over {len(files)} images, tolerance {args.tol:g}px")
    print(f"  precision {P:.3f}   recall {R:.3f}   "
          f"F1 {2 * P * R / (P + R) if P + R else 0:.3f}")
    print(f"  {tot_tp} matched, {tot_fp} false positives, {tot_fn} missed")
    if errs:
        print(f"  median placement error {np.median(errs):.2f}px")
    if cls_n:
        print(f"\nCLASS accuracy on {cls_n} matched, class-labelled points: "
              f"{cls_ok / cls_n:.3f}")
        for (want, got), n in confusion.most_common(8):
            print(f"  {n:5d}  {want:28s} -> {got}")

    # Tiles the labeller never reviewed hold marks that were never written down,
    # so a detection there is counted as a false positive when it may be correct.
    part = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    unswept = [p for p in part
               if p.get("tiles_total") and p.get("tiles_reviewed", 0) < p["tiles_total"]]
    if unswept:
        print(f"\n{len(unswept)} of {len(files)} images were not fully reviewed. "
              f"Precision there is a lower bound.")


if __name__ == "__main__":
    main()
