"""
Turn the labeller's JSON files into one CSV.

    python export.py labels/                 -> labels.csv
    python export.py labels/ -o train.csv
    python export.py labels/ --boxes 40      -> adds xmin,ymin,xmax,ymax

The CSV is `image,x,y,class`, which is the format build.py takes for `--seeds`
and score.py takes for predictions, so labels can be fed straight back in.

`--boxes` writes a square box of the given side around each point as well, for
detectors that want boxes rather than points. Pick the side from the size of the
thing you labelled, not from the default.

Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("labels", type=Path, help="folder of .json files from the labeller")
    ap.add_argument("-o", "--out", type=Path, default=Path("labels.csv"))
    ap.add_argument("--boxes", type=float, metavar="SIDE",
                    help="also write a square box of this side around each point")
    ap.add_argument("--skip-unswept", action="store_true",
                    help="drop images whose sweep grid was not finished")
    args = ap.parse_args()

    files = sorted(args.labels.glob("*.json"))
    if not files:
        raise SystemExit(f"no .json label files in {args.labels}")

    cols = ["image", "x", "y", "class"]
    if args.boxes:
        cols += ["xmin", "ymin", "xmax", "ymax"]

    rows, skipped, unclassed = [], [], 0
    for f in files:
        lab = json.loads(f.read_text(encoding="utf-8"))
        name = lab.get("image", f.stem)
        total, seen = lab.get("tiles_total"), lab.get("tiles_reviewed", 0)
        if args.skip_unswept and total and seen < total:
            skipped.append(f"{name} ({seen}/{total} tiles)")
            continue
        w, h = lab.get("width"), lab.get("height")
        for p in lab.get("points", []):
            if not p.get("cls"):
                unclassed += 1
            row = [name, p["x"], p["y"], p.get("cls") or ""]
            if args.boxes:
                s = args.boxes / 2
                x0, y0 = p["x"] - s, p["y"] - s
                x1, y1 = p["x"] + s, p["y"] + s
                if w and h:      # keep boxes inside the image
                    x0, y0 = max(0, x0), max(0, y0)
                    x1, y1 = min(w, x1), min(h, y1)
                row += [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]
            rows.append(row)

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(cols)
        wtr.writerows(rows)

    print(f"wrote {len(rows)} points from {len(files) - len(skipped)} images "
          f"to {args.out}")
    if unclassed:
        print(f"  {unclassed} points have no class (the class column is empty)")
    for s in skipped:
        print(f"  skipped, not fully swept: {s}")


if __name__ == "__main__":
    main()
