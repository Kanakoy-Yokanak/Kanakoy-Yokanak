#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

LOGIN = os.environ.get("GITHUB_LOGIN", "Kanakoy-Yokanak")
TOKEN = os.environ.get("CONTRIBUTIONS_TOKEN", "")
OUT_DIR = Path("assets")
GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = r'''
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        months { firstDay name totalWeeks year }
        weeks {
          firstDay
          contributionDays {
            date
            weekday
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
'''

THEMES = {
    "dark": {
        "root": "#0d1117", "panel": "#0d1117", "border": "#30363d",
        "text": "#f0f6fc", "muted": "#8b949e",
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "blue": "#1f6feb",
    },
    "light": {
        "root": "#ffffff", "panel": "#ffffff", "border": "#d0d7de",
        "text": "#1f2328", "muted": "#656d76",
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "blue": "#0969da",
    },
}

LEVEL_INDEX = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

WIDTH, HEIGHT = 1200, 265
GRID_X, GRID_Y = 86, 95
CELL, PITCH = 11, 14


def fetch_calendar() -> dict:
    if not TOKEN:
        raise RuntimeError(
            "CONTRIBUTIONS_TOKEN is required so the graph can include the same private/restricted contribution counts visible to the account owner."
        )
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "kanakoy-profile-contribution-renderer",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"]))
    user = payload.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {LOGIN}")
    return user["contributionsCollection"]["contributionCalendar"]


def month_positions(calendar: dict) -> list[tuple[str, int]]:
    weeks = calendar["weeks"]
    out = []
    last_x = -999
    for month in calendar["months"]:
        target = date.fromisoformat(month["firstDay"])
        idx = 0
        for i, week in enumerate(weeks):
            start = date.fromisoformat(week["firstDay"])
            if start <= target <= start + timedelta(days=6):
                idx = i
                break
            if start > target:
                idx = max(0, i - 1)
                break
        x = GRID_X + idx * PITCH
        if x - last_x >= 38:
            out.append((month["name"][:3], x))
            last_x = x
    return out


def render(calendar: dict, theme_name: str) -> str:
    t = THEMES[theme_name]
    weeks = calendar["weeks"]
    total = int(calendar["totalContributions"])
    last_day = max(
        date.fromisoformat(day["date"])
        for week in weeks
        for day in week["contributionDays"]
    )
    year = last_day.year

    cells = []
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            x = GRID_X + col * PITCH
            y = GRID_Y + int(day["weekday"]) * PITCH
            level = LEVEL_INDEX.get(day["contributionLevel"], 0)
            count = int(day["contributionCount"])
            label = f'{count} contribution{"s" if count != 1 else ""} on {day["date"]}'
            cells.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{t["levels"][level]}" data-date="{day["date"]}" data-level="{level}" data-count="{count}">'
                f'<title>{html.escape(label)}</title></rect>'
            )

    months = "".join(
        f'<text x="{x}" y="82" class="label">{html.escape(name)}</text>'
        for name, x in month_positions(calendar)
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
<title id="title">{total:,} contributions in the last year</title>
<desc id="desc">Automatically generated GitHub contribution calendar for {html.escape(LOGIN)}.</desc>
<style>
text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
.title{{fill:{t["text"]};font-size:19px;font-weight:400}}
.label{{fill:{t["text"]};font-size:13px}}
.muted{{fill:{t["muted"]};font-size:12px}}
</style>
<rect width="{WIDTH}" height="{HEIGHT}" fill="{t["root"]}"/>
<text x="20" y="32" class="title">{total:,} contributions in the last year</text>
<text x="805" y="31" class="muted">Contribution settings</text>
<path d="M928 25l5 5 5-5" fill="{t["muted"]}"/>
<rect x="1010" y="8" width="160" height="44" rx="7" fill="{t["blue"]}"/>
<text x="1090" y="35" text-anchor="middle" fill="#fff" font-size="14">{year}</text>
<rect x="20" y="54" width="960" height="176" rx="7" fill="{t["panel"]}" stroke="{t["border"]}"/>
{months}
<text x="46" y="{GRID_Y + PITCH + 9}" class="label">Mon</text>
<text x="46" y="{GRID_Y + 3*PITCH + 9}" class="label">Wed</text>
<text x="46" y="{GRID_Y + 5*PITCH + 9}" class="label">Fri</text>
<g>{''.join(cells)}</g>
<text x="70" y="213" class="muted">Learn how we count contributions</text>
<text x="720" y="213" class="muted">Less</text>
<rect x="754" y="204" width="11" height="11" rx="2" fill="{t["levels"][0]}"/>
<rect x="771" y="204" width="11" height="11" rx="2" fill="{t["levels"][1]}"/>
<rect x="788" y="204" width="11" height="11" rx="2" fill="{t["levels"][2]}"/>
<rect x="805" y="204" width="11" height="11" rx="2" fill="{t["levels"][3]}"/>
<rect x="822" y="204" width="11" height="11" rx="2" fill="{t["levels"][4]}"/>
<text x="840" y="213" class="muted">More</text>
</svg>
'''


def main() -> int:
    calendar = fetch_calendar()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = OUT_DIR / f"contributions-{theme}.svg"
        path.write_text(render(calendar, theme), encoding="utf-8")
        print(f"wrote {path}")
    print(f"totalContributions={calendar['totalContributions']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
