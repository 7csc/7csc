"""Generate assets/landscape.svg: a scrolling pixel landscape drawn on a GitHub contribution-graph grid."""

import math
import random
from pathlib import Path

COLS, ROWS = 53, 12
CELL, GAP = 10, 3
PITCH = CELL + GAP
PAD = 10
W, H = PAD * 2 + COLS * PITCH - GAP, PAD * 2 + ROWS * PITCH - GAP

BG = "#0d1117"
L = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

random.seed(7)


def rect(x, y, level, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<rect x="{PAD + x * PITCH}" y="{PAD + y * PITCH}" width="{CELL}" height="{CELL}" rx="2" fill="{L[level]}"{c}/>'


def ridge(period, peaks):
    """Height per column from (center, height, slope) peaks, wrapping at period."""
    h = [0] * period
    for cx, ph, slope in peaks:
        for x in range(period):
            d = min(abs(x - cx), period - abs(x - cx))
            h[x] = max(h[x], ph - math.floor(d / slope))
    return h


def far_mountains():
    period = 64
    h = ridge(period, [(8, 7, 1), (22, 5, 1), (37, 8, 1), (52, 6, 1)])
    cells = {}
    for x in range(period):
        for k in range(h[x]):
            # snow caps on the tall peaks
            cells[(x, ROWS - 3 - k)] = 2 if h[x] >= 6 and k >= h[x] - 2 else 1
    return period, cells


def near_hills():
    period = 44
    h = ridge(period, [(6, 2, 3), (20, 3, 3), (34, 2, 3)])
    return period, {(x, ROWS - 3 - k): 2 for x in range(period) for k in range(h[x])}


def trees_and_ground():
    period = 36
    cells = {}
    for x in range(period):
        cells[(x, ROWS - 2)] = 4 if random.random() < 0.15 else 3  # grass with flowers
        cells[(x, ROWS - 1)] = 1  # soil
    for tx, size in [(3, 3), (12, 2), (19, 3), (27, 2), (31, 3)]:
        cells[(tx, ROWS - 3)] = 2  # trunk
        top = ROWS - 3 - size
        cells[(tx, top)] = 4
        for dy in range(1, size):
            for dx in (-1, 0, 1):
                cells[((tx + dx) % period, top + dy)] = 4
    return period, cells


def clouds():
    period = 80
    cells = {}
    for cx, cy, w in [(8, 2, 4), (30, 1, 3), (52, 2, 5), (68, 1, 3)]:
        for dx in range(w):
            cells[((cx + dx) % period, cy)] = 1
        for dx in range(1, w - 1):
            cells[((cx + dx) % period, cy - 1)] = 1
    return period, cells


def layer(name, period, cells, ms_per_col):
    reps = math.ceil((COLS + period) / period)
    rects = [rect(x + r * period, y, lv) for r in range(reps) for (x, y), lv in cells.items()]
    anim = (
        f"@keyframes {name}{{to{{transform:translateX(-{period * PITCH}px)}}}}"
        f".{name}{{animation:{name} {period * ms_per_col}ms steps({period}) infinite}}"
    )
    return anim, f'<g class="{name}">{"".join(rects)}</g>'


def main():
    styles, body = [], []

    body.extend(rect(x, y, 0) for x in range(COLS) for y in range(ROWS))

    # moon (crescent) and twinkling stars stay fixed in the sky
    for x, y in [(45, 1), (46, 1), (44, 2), (44, 3), (45, 4), (46, 4)]:
        body.append(rect(x, y, 4))
    stars = [(3, 0), (11, 3), (19, 1), (26, 4), (34, 0), (40, 2), (50, 3)]
    for i, (x, y) in enumerate(stars):
        body.append(rect(x, y, 2, f"s s{i}"))
        styles.append(f".s{i}{{animation-delay:{i * 470}ms}}")
    styles.append("@keyframes tw{0%,100%{opacity:0}50%{opacity:1}}.s{opacity:0;animation:tw 3.2s ease-in-out infinite}")

    for name, (period, cells), speed in [
        ("cl", clouds(), 900),
        ("fm", far_mountains(), 600),
        ("nh", near_hills(), 350),
        ("tr", trees_and_ground(), 180),
    ]:
        anim, g = layer(name, period, cells, speed)
        styles.append(anim)
        body.append(f'<g clip-path="url(#v)">{g}</g>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        f"<style>{''.join(styles)}</style>"
        f'<defs><clipPath id="v"><rect x="{PAD}" y="{PAD}" width="{COLS * PITCH - GAP}" height="{ROWS * PITCH - GAP}"/></clipPath></defs>'
        f'<rect width="{W}" height="{H}" rx="6" fill="{BG}"/>'
        f"{''.join(body)}</svg>\n"
    )
    Path(__file__).with_name("landscape.svg").write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
