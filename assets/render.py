"""Render the profile artwork from live GitHub data.

- landscape.svg: a night seaside town whose skyline is the last 53 weeks of contributions
  (one building per week, one lit floor per active day) under the real current moon phase.
- almanac.svg: pixel-digit stats and the contribution calendar in the same palette.

Data comes from the GitHub GraphQL API using GITHUB_TOKEN (or GH_TOKEN).
Without a token a deterministic fake year is used so the art still renders.
"""

import datetime as dt
import json
import math
import os
import random
import urllib.error
import urllib.request
from pathlib import Path

USER = "7csc"
OUT = Path(__file__).parent

COLS = 53
CELL, GAP = 10, 3
PITCH = CELL + GAP
PAD = 10
W = PAD * 2 + COLS * PITCH - GAP

BG = "#0d1117"
SKY_TOP, SKY_BOTTOM = "#0c1030", "#9a4a78"
SEA = ["#1b3f6b", "#163560", "#122b52", "#0e2244", "#0a1a36"]
STAR = "#e6edf3"
MOON, MOON_DARK = "#ffd76a", "#2a2446"
NEON = "#ff5fa2"
MOUNTAIN, SNOW = "#4b3f8c", "#a39be0"
WINDOWS = ["#2b2540", "#9c6f2c", "#e0a83a", "#ffd76a"]  # contribution quartiles 1..4
BEACON = "#ff4d4d"
BUILDINGS = ["#0f1126", "#161a33"]
WAVE = ["#3d7fc1", "#5aa0e0"]
CAL = ["#1a1d3d", "#4b3f8c", "#9a4a78", "#ff5fa2", "#ffd76a"]
TEXT, MUTED = "#c9d1d9", "#8b949e"
FONT_FAMILY = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

GLYPHS = {
    "7": ["####", "...#", "..#.", ".#..", ".#.."],
    "c": [".###", "#...", "#...", "#...", ".###"],
    "s": [".###", "#...", ".##.", "...#", "###."],
}
DIGITS = {
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"],
    "3": ["###", "..#", ".##", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", "..#", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "###"],
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes { stargazerCount }
    }
  }
}
"""


# ---------------------------------------------------------------- data


def query(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req))["data"]["user"]


def fetch():
    # GH_TOKEN (a PAT) also sees private contributions; fall back to the Actions token if it is missing or expired
    tokens = [t for t in (os.environ.get("GH_TOKEN"), os.environ.get("GITHUB_TOKEN")) if t]
    if not tokens:
        return fake_data()
    for i, token in enumerate(tokens):
        try:
            user = query(token)
            break
        except urllib.error.HTTPError as e:
            if e.code != 401 or i == len(tokens) - 1:
                raise
            print("token rejected (401), trying the next one")
    cal = user["contributionsCollection"]["contributionCalendar"]
    return {
        "weeks": [
            [(d["date"], d["weekday"], d["contributionCount"], LEVEL[d["contributionLevel"]]) for d in w["contributionDays"]]
            for w in cal["weeks"]
        ][-COLS:],
        "total": cal["totalContributions"],
        "followers": user["followers"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in user["repositories"]["nodes"]),
    }


def fake_data():
    rnd = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday() + 1 + 52 * 7)
    weeks, total = [], 0
    for w in range(COLS):
        days = []
        for d in range(7):
            date = start + dt.timedelta(days=w * 7 + d)
            if date > today:
                break
            n = rnd.choice([0, 0, 1, 3, 8, 15])
            total += n
            days.append((date.isoformat(), d, n, min(4, (n + 3) // 4)))
        weeks.append(days)
    return {"weeks": weeks, "total": total, "followers": 0, "repos": 0, "stars": 0}


def streaks(days):
    longest = run = 0
    for _, _, n, _ in days:
        run = run + 1 if n else 0
        longest = max(longest, run)
    current = 0
    tail = days[:-1] if days and days[-1][2] == 0 else days  # today may still be empty
    for _, _, n, _ in reversed(tail):
        if not n:
            break
        current += 1
    return current, longest


def moon_phase(now):
    """0 = new moon, 0.5 = full moon."""
    known_new = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
    return ((now - known_new).total_seconds() / 86400 / 29.530588853) % 1


# ---------------------------------------------------------------- drawing


def mix(a, b, t):
    ca = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def rect(x, y, color, cls="", delay=None, ox=PAD, oy=PAD):
    c = f' class="{cls}"' if cls else ""
    if delay is not None:
        c += f' style="animation-delay:{delay}ms"'
    return f'<rect x="{ox + x * PITCH}" y="{oy + y * PITCH}" width="{CELL}" height="{CELL}" rx="2" fill="{color}"{c}/>'


def text(x, y, s, color=TEXT, size=11, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="{FONT_FAMILY}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{s}</text>'
    )


def svg(width, height, styles, body, clip_h):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f"<style>{''.join(styles)}</style>"
        f'<defs><clipPath id="v"><rect x="{PAD}" y="{PAD}" width="{COLS * PITCH - GAP}" height="{clip_h}"/></clipPath></defs>'
        f'<rect width="{width}" height="{height}" rx="6" fill="{BG}"/>'
        f"{''.join(body)}</svg>\n"
    )


def ridge(period, peaks):
    h = [0] * period
    for cx, ph in peaks:
        for x in range(period):
            d = min(abs(x - cx), period - abs(x - cx))
            h[x] = max(h[x], ph - d)
    return h


def scrolling(name, period, cells, ms_per_col, rnd):
    reps = math.ceil((COLS + period) / period)
    rects = [
        rect(x + r * period, y, c, cls, rnd.randint(0, 2600) if cls else None)
        for r in range(reps)
        for (x, y), (c, cls) in cells.items()
    ]
    anim = (
        f"@keyframes {name}{{to{{transform:translateX(-{period * PITCH}px)}}}}"
        f".{name}{{animation:{name} {period * ms_per_col}ms steps({period}) infinite}}"
    )
    return anim, f'<g clip-path="url(#v)"><g class="{name}">{"".join(rects)}</g></g>'


BLINK = [
    "@keyframes tw{0%,100%{opacity:0}50%{opacity:1}}.s{opacity:0;animation:tw 3.2s ease-in-out infinite}",
    "@keyframes fl{0%,100%{opacity:1}50%{opacity:.3}}.f{animation:fl 2.6s steps(2) infinite}",
    "@keyframes gl{0%,100%{opacity:1}50%{opacity:.35}}.r{animation:gl 1.8s steps(3) infinite}",
    "@keyframes bc{0%,60%{opacity:1}61%,100%{opacity:.15}}.b{animation:bc 1.4s steps(1) infinite}",
]


def landscape(data, now):
    rows, horizon = 14, 10
    rnd = random.Random(7)
    styles, body = list(BLINK), []

    for y in range(rows):
        color = mix(SKY_TOP, SKY_BOTTOM, y / horizon) if y <= horizon else SEA[y - horizon - 1]
        body.extend(rect(x, y, color) for x in range(COLS))

    for i, (x, y) in enumerate([(24, 0), (27, 3), (31, 1), (35, 4), (38, 0), (41, 2), (51, 4), (1, 6), (20, 6), (52, 1)]):
        body.append(rect(x, y, STAR, "s", i * 330))

    # the real moon phase: waxing lights the right side, waning the left
    phase = moon_phase(now)
    mx, my, r = 46, 3, 2.5
    k = math.cos(2 * math.pi * phase)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx * dx + dy * dy > r * r:
                continue
            nx, half = dx / r, math.sqrt(max(0.0, 1 - (dy / r) ** 2))
            lit = nx > half * k if phase < 0.5 else nx < -half * k
            body.append(rect(mx + dx, my + dy, MOON if lit else MOON_DARK))

    # far mountains drift slowly behind the town
    period = 64
    h = ridge(period, [(8, 6), (24, 4), (38, 7), (53, 5)])
    cells = {}
    for x in range(period):
        for k2 in range(h[x]):
            cells[(x, horizon - k2)] = (SNOW if h[x] >= 6 and k2 >= h[x] - 2 else MOUNTAIN, "")
    anim, g = scrolling("mt", period, cells, 700, rnd)
    styles.append(anim)
    body.append(g)

    # the town: one building per week, taller for busier weeks (ranked within the year); one lit window per active day
    totals = [sum(d[2] for d in week) for week in data["weeks"]]
    ranked = sorted(totals)
    for x, (week, total) in enumerate(zip(data["weeks"], totals)):
        pct = ranked.index(total) / max(1, len(ranked) - 1)
        height = 0 if not total else 2 + round(4 * pct)
        levels = sorted((d[3] for d in week), reverse=True)
        for k2 in range(height):
            lv = levels[k2] if k2 < len(levels) else 0
            if lv >= 1:
                cls = "f" if lv == 4 and rnd.random() < 0.4 else ""
                body.append(rect(x, horizon - k2, WINDOWS[lv - 1], cls, rnd.randint(0, 2600) if cls else None))
            else:
                body.append(rect(x, horizon - k2, BUILDINGS[x % 2]))
        if x == len(totals) - 1:
            body.append(rect(x, horizon - height, BEACON, "b"))  # this week's rooftop beacon

    cells = {}
    for y in range(horizon + 1, rows):
        for x in range(30):
            if rnd.random() < 0.12:
                cells[(x, y)] = (rnd.choice(WAVE), "")
    anim, g = scrolling("wv", 30, cells, 160, rnd)
    styles.append(anim)
    body.append(g)

    # moonlight on the water, brighter the fuller the moon
    fullness = 1 - abs(phase - 0.5) * 2
    for y in range(horizon + 1, rows):
        spread = (y - horizon) // 2
        for x in range(mx - 1 - spread, mx + 2 + spread):
            if rnd.random() < 0.25 + 0.45 * fullness:
                color = MOON if y < horizon + 2 else mix(MOON, SEA[0], 0.4)
                body.append(rect(x, y, color, "r", rnd.randint(0, 1800)))

    x0 = 3
    for ch in "7csc":
        for dy, row in enumerate(GLYPHS[ch]):
            for dx, px in enumerate(row):
                if px == "#":
                    body.append(rect(x0 + dx, dy, NEON))
        x0 += len(GLYPHS[ch][0]) + 1

    height = PAD * 2 + rows * PITCH - GAP
    return svg(W, height, styles, body, rows * PITCH - GAP)


def pixel_number(n, x, y, color):
    out = []
    for ch in f"{n}":
        for dy, row in enumerate(DIGITS[ch]):
            for dx, px in enumerate(row):
                if px == "#":
                    out.append(rect(dx, dy, color, ox=x, oy=y))
        x += 4 * PITCH
    return out, x


def almanac(data, now):
    days = [d for w in data["weeks"] for d in w]
    current, longest = streaks(days)
    active = sum(1 for d in days if d[2])
    busiest = max(days, key=lambda d: d[2])

    body = [text(PAD, PAD + 8, f"~/{USER}/almanac  {days[0][0]} → {days[-1][0]}", MUTED)]

    y = PAD + 22
    digits, right = pixel_number(data["total"], PAD, y, NEON)
    body.extend(digits)
    body.append(text(PAD, y + 5 * PITCH + 14, "contributions / last 53 weeks", NEON, 11, 600))

    lx = max(right + 24, PAD + 250)
    lines = [
        ("current streak", f"{current} days"),
        ("longest streak", f"{longest} days"),
        ("active days", f"{active} / {len(days)}"),
        ("busiest day", f"{busiest[0]} · {busiest[2]}"),
    ]
    for i, (k, v) in enumerate(lines):
        body.append(text(lx, y + 9 + i * 17, k, MUTED))
        body.append(text(lx + 120, y + 9 + i * 17, v, TEXT, 11, 600))
    rx = W - PAD
    for i, (k, v) in enumerate([("★ stars", data["stars"]), ("followers", data["followers"]), ("public repos", data["repos"])]):
        body.append(text(rx - 34, y + 9 + i * 17, k, MUTED, anchor="end"))
        body.append(text(rx, y + 9 + i * 17, v, MOON, 11, 600, anchor="end"))

    cy = y + 5 * PITCH + 34
    for x, week in enumerate(data["weeks"]):
        for date, wd, n, lv in week:
            body.append(rect(x, wd, CAL[lv], oy=cy))

    # a scan line sweeping the year
    sweep_ms = COLS * 90
    styles = [
        f"@keyframes sw{{from{{transform:translateX(0)}}to{{transform:translateX({COLS * PITCH}px)}}}}"
        f".sw{{animation:sw {sweep_ms}ms steps({COLS}) infinite}}"
    ]
    body.append(
        f'<rect class="sw" x="{PAD - 1}" y="{cy - 3}" width="{CELL + 2}" height="{7 * PITCH + 3}" rx="3" '
        f'fill="none" stroke="{MOON}" stroke-opacity=".8" stroke-width="1.5"/>'
    )

    ly = cy + 7 * PITCH + 14
    body.append(text(PAD, ly, f"rendered {days[-1][0]} · daily via GitHub Actions", MUTED, 10))
    lx = W - PAD - 5 * 14 - 34
    body.append(text(lx - 6, ly, "less", MUTED, 10, anchor="end"))
    for i, c in enumerate(CAL):
        body.append(f'<rect x="{lx + i * 14}" y="{ly - 9}" width="10" height="10" rx="2" fill="{c}"/>')
    body.append(text(lx + 5 * 14 + 2, ly, "more", MUTED, 10))

    return svg(W, ly + PAD, styles, body, 0)


def main():
    now = dt.datetime.now(dt.timezone.utc)
    data = fetch()
    (OUT / "landscape.svg").write_text(landscape(data, now), encoding="utf-8")
    (OUT / "almanac.svg").write_text(almanac(data, now), encoding="utf-8")


if __name__ == "__main__":
    main()
