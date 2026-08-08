"""
Build one self-contained labelling page per image.

Each page carries its image inline, so the output folder can be zipped, emailed,
or opened from a file:// URL with no server and no install. Nothing is uploaded
anywhere.

    python build.py images/
    python build.py images/ --classes classes.json
    python build.py images/ --seeds seeds.csv --out pages/

Then open pages/index.html, label, press S, and the JSON downloads.

Only the standard library is used, so this runs on a bare Python 3.8+.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import os
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = HERE / "labeller.html"
SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def load_classes(path: Path | None) -> list[dict]:
    """Class list for the palette.

    Accepts either a bare list of names or a list of objects with `name`, and
    optionally `color` and `glyph`. A glyph is a path to a small image of the
    marker itself, which matters when two classes share a colour and differ only
    in shape — a colour swatch cannot tell those apart.
    """
    if path is None:
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for i, item in enumerate(raw):
        c = {"name": item, "color": PALETTE[i % len(PALETTE)]} \
            if isinstance(item, str) else dict(item)
        c.setdefault("color", PALETTE[i % len(PALETTE)])
        if c.get("glyph"):
            g = (path.parent / c["glyph"]).resolve()
            c["glyph"] = data_uri(g) if g.exists() else ""
        out.append(c)
    return out


# Distinguishable at a glance and separable for the common colour-vision
# deficiencies; the first two are the pair most often needed.
PALETTE = ["#2b6fe0", "#eb6834", "#3aa757", "#d436b8", "#e8c020",
           "#25c4d6", "#e5352b", "#7a5cd0", "#9aa0a6"]


def load_seeds(path: Path | None) -> dict[str, list[dict]]:
    """Pre-existing points per image, from `image,x,y[,class]` rows.

    Seeds turn labelling into correction, which is much faster — but only when
    they are mostly right. A seed set several times larger than the real count
    costs more to delete than to draw, so pass a detector's confident output
    rather than everything it produced.
    """
    if path is None:
        return {}
    seeds: dict[str, list[dict]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seeds[os.path.basename(row["image"])].append({
                "x": round(float(row["x"]), 1),
                "y": round(float(row["y"]), 1),
                "cls": (row.get("class") or "").strip() or None,
            })
    return seeds


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", help="folder of images, or a single image")
    ap.add_argument("--out", default="pages", help="output folder (default: pages)")
    ap.add_argument("--classes", type=Path, help="JSON list of class names or objects")
    ap.add_argument("--seeds", type=Path, help="CSV of image,x,y[,class] to pre-fill")
    ap.add_argument("--blind", type=int, default=0, metavar="N",
                    help="leave N images unseeded as a control on seeding bias")
    ap.add_argument("--tile", type=int, default=220,
                    help="sweep-grid tile size in image pixels (default: 220)")
    args = ap.parse_args()

    src = Path(args.images)
    files = sorted(p for p in ([src] if src.is_file() else src.iterdir())
                   if p.suffix.lower() in SUFFIXES)
    if not files:
        raise SystemExit(f"no images found in {src}")

    classes = load_classes(args.classes)
    seeds = load_seeds(args.seeds)
    template = TEMPLATE.read_text(encoding="utf-8")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Control images, spread through the set rather than taken from one end so
    # they are not all the same kind of scene. Someone shown a detector's output
    # tends to confirm it rather than hunt for what it missed, and comparing
    # points-per-image on these against the seeded ones is what shows whether
    # that happened.
    blind = set()
    if args.blind > 0 and seeds:
        n = min(args.blind, len(files))
        blind = {files[round(i * (len(files) - 1) / max(n - 1, 1))].name
                 for i in range(n)} if n > 1 else {files[len(files) // 2].name}

    pages = [f.stem + ".html" for f in files]
    for i, f in enumerate(files):
        data = {
            "image_name": f.name,
            "image": data_uri(f),
            "classes": classes,
            "seeds": [] if f.name in blind else seeds.get(f.name, []),
            "tile": args.tile,
            "prev": pages[i - 1] if i else None,
            "next": pages[i + 1] if i + 1 < len(pages) else None,
        }
        page = (template.replace("__DATA__", json.dumps(data))
                        .replace("__TITLE__", f.name))
        (out / pages[i]).write_text(page, encoding="utf-8")
        print(f"  {f.name:40s} {len(data['seeds']):5d} seeds"
              f"{'   [blind control]' if f.name in blind else ''}")

    rows = "\n".join(
        f'<li><a href="{p}">{f.name}</a> '
        f'<small>{len(seeds.get(f.name, []))} seeds</small></li>'
        for f, p in zip(files, pages))
    (out / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>click-to-label</title>"
        "<style>body{font:14px/1.7 ui-sans-serif,system-ui,sans-serif;max-width:44rem;"
        "margin:3rem auto;padding:0 1rem}small{color:#6b6b6b}li{margin:.2rem 0}</style>"
        f"<h1>click-to-label</h1><p>{len(files)} images, "
        f"{len(classes)} classes.</p><ol>{rows}</ol>", encoding="utf-8")

    print(f"\nwrote {len(files)} pages to {out}/")
    print(f"open {out / 'index.html'}")


if __name__ == "__main__":
    main()
