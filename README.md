# click-to-label

Point-label images in the browser. No install, no server, nothing uploaded.

`build.py` turns a folder of images into one self-contained HTML page each. Open a page, click on things, press `S`, and a JSON file lands in your downloads. `score.py` then measures a model's predictions against what you labelled.

![the labeller, with 83 points placed across four classes](docs/screenshot.png)

```bash
python build.py my-images/
# open pages/index.html, label, press S
```

That is the whole dependency list for labelling: Python 3.8 and a browser. `score.py` also wants numpy.

## Why this exists

I was recovering bird annotations from historical aerial surveys, where the original tool had drawn coloured dots straight into screenshots and never saved the coordinates. My pipeline could find those dots, but the survey data only gave a **count** per image, never a position. So "found 61 dots" against "61 dots present" was the entire measurement available, and that number cannot separate:

- found all 61 markers
- found 40 real ones and invented 21
- found 61, none of them on anything

All three score 61. Precision, recall and placement error were unmeasurable, so I could not tell whether a change helped.

I tried the established annotation tools first. They are built for drawing boxes and polygons across a team, with a server, accounts and a project model. I wanted to click 500 dots on eight images, on my own laptop, in an afternoon. This is that.

The first frames I labelled with it found a bug that had been discarding **27% of every image's real markers** while the count metric read a healthy 1.24x. That is the argument for labelling a small set by hand even when you already have counts.

## Labelling

| | |
|---|---|
| **Click** empty space | add a point |
| **Click** a point, with a class selected | assign that class |
| **Click** a point, with no class selected | delete it |
| **Shift+click** | always delete |
| **Drag** / **Wheel** | pan / zoom |
| **1**–**9** | pick a class |
| **N** | jump to the next unclassified point |
| **S** | save · **U** undo · **H** hide points |

Pick a class first, then click every point of that class across the whole image, then move to the next class. That is much faster than choosing a class for each point in turn.

## Four things it does deliberately

**Autosaves after every click.** Labelling a busy image takes an hour and a stray refresh should not cost it. State goes to `localStorage` and the page offers it back when you return.

**Tracks a sweep grid.** A tile only clears once you have viewed it at 2x zoom or closer, because small marks are invisible below that and an unreviewed tile is exactly where a missed one hides. Saving with tiles outstanding asks you to confirm. This matters more than it sounds: a half-reviewed image produces labels that look like a detector failure when the failure is in the labelling.

**Takes seeds, so you correct rather than create.** Pass a detector's output with `--seeds` and its points are already on the image. Feed it confident output, not everything the model produced: a seed set several times larger than the real count costs more to delete than to draw.

**Shows glyphs, not just colour swatches.** If two classes share a colour and differ only in marker shape, a coloured square in the palette cannot tell them apart. Point a class at a small image of its own marker and the palette shows that instead.

## Scoring

```bash
python score.py labels/ predictions.csv
```

`predictions.csv` is `image,x,y[,class]`, the same format `--seeds` takes, so one file feeds both. Predictions are matched to labels one-to-one, closest first, within a pixel tolerance:

```
POOLED over 8 images, tolerance 5px
  precision 0.190   recall 0.678   F1 0.297
  367 matched, 1564 false positives, 174 missed
  median placement error 1.51px

CLASS accuracy on 215 matched, class-labelled points: 0.544
     19  WHIB site                    -> WHIB adult
     14  row 2 (green)                -> none
```

The pairing is greedy over a global distance ordering rather than per-prediction nearest. Nearest-first lets two predictions claim the same label, which reports a miss and a false positive that are really one duplicate.

It also warns when an image was not fully swept, because precision measured against a partly-labelled image is a lower bound rather than a result.

## Files

```
build.py        images -> pages          stdlib only
labeller.html   the page itself          no dependencies
score.py        predictions -> P/R/F1    numpy
examples/       two aerial images, classes, seeds
```

**Classes** (`--classes classes.json`), either bare names or objects:

```json
[
  { "name": "adult bird", "color": "#2b6fe0" },
  { "name": "nest site",  "color": "#eb6834", "glyph": "glyphs/nest.png" }
]
```

**Output**, one JSON per image:

```json
{
  "image": "aerial-survey-colony.jpg",
  "width": 880, "height": 470,
  "tiles_total": 12, "tiles_reviewed": 12,
  "seeded": true, "seed_count": 83,
  "points": [ { "x": 412.0, "y": 233.5, "cls": "adult bird" } ]
}
```

## Try it

```bash
python build.py examples/images --classes examples/classes.json --seeds examples/seeds.csv
# open pages/index.html
```

Two aerial survey screenshots. The colony image comes pre-seeded with 83 real hand-labelled points, which is what the screenshot above shows; the sparse one has two, so you can see what starting from nearly nothing feels like.

## What it is not

Not a replacement for CVAT or Label Studio. There are no boxes, no polygons, no masks, no multi-user anything, no review workflow. It labels points, on your own machine, and gets out of the way.

MIT licensed. Built while working on [Recovering Bird Annotations from Historical Airborne Imagery](https://github.com/vickysharma-prog/Recovering-computer-vision-annotations) for Google Summer of Code 2026 with DeepForest / WeeCology.
