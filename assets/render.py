"""Render the profile almanac from live GitHub data.

- almanac.svg: pixel-digit stats and the contribution calendar.

Data comes from the GitHub GraphQL API using GITHUB_TOKEN (or GH_TOKEN).
Without a token a deterministic fake year is used so the almanac still renders.
"""

import datetime as dt
import json
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
MOON = "#ffd76a"
NEON = "#ff5fa2"
CAL = ["#1a1d3d", "#4b3f8c", "#9a4a78", "#ff5fa2", "#ffd76a"]
TEXT, MUTED = "#c9d1d9", "#8b949e"
FONT_FAMILY = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

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


# ---------------------------------------------------------------- drawing


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


def pixel_number(n, x, y, color):
    out = []
    for ch in f"{n}":
        for dy, row in enumerate(DIGITS[ch]):
            for dx, px in enumerate(row):
                if px == "#":
                    out.append(rect(dx, dy, color, ox=x, oy=y))
        x += 4 * PITCH
    return out, x


def almanac(data):
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
    data = fetch()
    (OUT / "almanac.svg").write_text(almanac(data), encoding="utf-8")


if __name__ == "__main__":
    main()
