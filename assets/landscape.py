"""Generate assets/landscape.svg: a scrolling night seaside town drawn on a GitHub contribution-graph grid."""

import math
import random
from pathlib import Path

COLS, ROWS = 53, 16
CELL, GAP = 10, 3
PITCH = CELL + GAP
PAD = 10
W, H = PAD * 2 + COLS * PITCH - GAP, PAD * 2 + ROWS * PITCH - GAP
HORIZON = 10  # last row of land; sea starts below

BG = "#0d1117"
SKY_TOP, SKY_BOTTOM = "#0c1030", "#9a4a78"
SEA = ["#1b3f6b", "#163560", "#122b52", "#0e2244", "#0a1a36"]
STAR = "#e6edf3"
MOON = "#ffd76a"
NEON = "#ff5fa2"
MOUNTAIN, SNOW = "#4b3f8c", "#a39be0"
BUILDINGS = ["#0f1126", "#14172f", "#111428"]
WINDOW = "#ffcc4d"
WAVE = ["#3d7fc1", "#5aa0e0"]

random.seed(7)

FONT = {
    "7": ["####", "...#", "..#.", ".#..", ".#.."],
    "c": [".###", "#...", "#...", "#...", ".###"],
    "s": [".###", "#...", ".##.", "...#", "###."],
}


def mix(a, b, t):
    ca = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def rect(x, y, color, cls="", delay=None):
    c = f' class="{cls}"' if cls else ""
    if delay is not None:
        c += f' style="animation-delay:{delay}ms"'
    return f'<rect x="{PAD + x * PITCH}" y="{PAD + y * PITCH}" width="{CELL}" height="{CELL}" rx="2" fill="{color}"{c}/>'


def ridge(period, peaks):
    """Height per column from (center, height, slope) peaks, wrapping at period."""
    h = [0] * period
    for cx, ph, slope in peaks:
        for x in range(period):
            d = min(abs(x - cx), period - abs(x - cx))
            h[x] = max(h[x], ph - math.floor(d / slope))
    return h


def mountains():
    period = 64
    h = ridge(period, [(8, 7, 1), (24, 5, 1), (38, 8, 1), (53, 6, 1)])
    cells = {}
    for x in range(period):
        for k in range(h[x]):
            cells[(x, HORIZON - k)] = (SNOW if h[x] >= 6 and k >= h[x] - 2 else MOUNTAIN, "")
    return period, cells


def city():
    period = 48
    cells = {}
    x = 0
    while x < period - 2:
        w, hgt = random.randint(2, 4), random.randint(2, 5)
        color = random.choice(BUILDINGS)
        for dx in range(w):
            for k in range(hgt):
                cells[(x + dx, HORIZON - k)] = (color, "")
        # lit windows, a few of them flicker
        for dx in range(w):
            for k in range(1, hgt):
                if random.random() < 0.22:
                    cells[(x + dx, HORIZON - k)] = (WINDOW, "f" if random.random() < 0.3 else "")
        x += w + random.choice([0, 1, 1, 2, 3])
    return period, cells


def waves():
    period = 30
    cells = {}
    for y in range(HORIZON + 1, ROWS):
        for x in range(period):
            if random.random() < 0.12:
                cells[(x, y)] = (random.choice(WAVE), "")
    return period, cells


def layer(name, period, cells, ms_per_col):
    reps = math.ceil((COLS + period) / period)
    rects = [rect(x + r * period, y, c, cls, random.randint(0, 2600) if cls else None) for r in range(reps) for (x, y), (c, cls) in cells.items()]
    anim = (
        f"@keyframes {name}{{to{{transform:translateX(-{period * PITCH}px)}}}}"
        f".{name}{{animation:{name} {period * ms_per_col}ms steps({period}) infinite}}"
    )
    return anim, f'<g clip-path="url(#v)"><g class="{name}">{"".join(rects)}</g></g>'


def main():
    styles = [
        "@keyframes tw{0%,100%{opacity:0}50%{opacity:1}}.s{opacity:0;animation:tw 3.2s ease-in-out infinite}",
        "@keyframes fl{0%,100%{opacity:1}50%{opacity:.25}}.f{animation:fl 2.6s steps(2) infinite}",
        "@keyframes gl{0%,100%{opacity:1}50%{opacity:.35}}.r{animation:gl 1.8s steps(3) infinite}",
    ]
    body = []

    # sky gradient and sea bands
    for y in range(ROWS):
        color = mix(SKY_TOP, SKY_BOTTOM, y / HORIZON) if y <= HORIZON else SEA[y - HORIZON - 1]
        body.extend(rect(x, y, color) for x in range(COLS))

    stars = [(24, 0), (27, 3), (31, 1), (35, 4), (38, 0), (42, 2), (50, 4), (1, 7), (20, 6), (52, 0)]
    for i, (x, y) in enumerate(stars):
        body.append(rect(x, y, STAR, "s", i * 330))

    moon_x = 45
    for x, y in [(moon_x, 1), (moon_x + 1, 1), (moon_x - 1, 2), (moon_x - 1, 3), (moon_x, 4), (moon_x + 1, 4)]:
        body.append(rect(x, y, MOON))

    for name, (period, cells), speed in [
        ("mt", mountains(), 700),
        ("ct", city(), 300),
        ("wv", waves(), 160),
    ]:
        anim, g = layer(name, period, cells, speed)
        styles.append(anim)
        body.append(g)

    # moon reflection on the sea
    for y in range(HORIZON + 1, ROWS):
        spread = (y - HORIZON) // 2
        for x in range(moon_x - spread, moon_x + 2 + spread):
            if random.random() < 0.6:
                color = MOON if y < HORIZON + 3 else mix(MOON, SEA[0], 0.4)
                body.append(rect(x, y, color, "r", random.randint(0, 1800)))

    # neon sign
    x0, y0 = 3, 1
    for ch in "7csc":
        for dy, row in enumerate(FONT[ch]):
            for dx, px in enumerate(row):
                if px == "#":
                    body.append(rect(x0 + dx, y0 + dy, NEON))
        x0 += len(FONT[ch][0]) + 1

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
