#!/usr/bin/env python3
# Render GitHub-style contribution calendars for the profile README.

from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

GRAPHQL_URL = "https://api.github.com/graphql"
LOGIN = os.environ.get("GITHUB_LOGIN", "Kanakoy-Yokanak")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR = Path("assets")

QUERY = r'''
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        months {
          firstDay
          name
          totalWeeks
          year
        }
        weeks {
          firstDay
          contributionDays {
            color
            contributionCount
            contributionLevel
            date
            weekday
          }
        }
      }
    }
  }
}
'''

THEMES = {
    "dark": {
        "root": "#0d1117",
        "panel": "#0d1117",
        "border": "#30363d",
        "text": "#f0f6fc",
        "muted": "#8b949e",
        "empty": "#161b22",
        "levels": {
            "NONE": "#161b22",
            "FIRST_QUARTILE": "#0e4429",
            "SECOND_QUARTILE": "#006d32",
            "THIRD_QUARTILE": "#26a641",
            "FOURTH_QUARTILE": "#39d353",
        },
        "blue": "#1f6feb",
        "blue_text": "#ffffff",
    },
    "light": {
        "root": "#ffffff",
        "panel": "#ffffff",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#656d76",
        "empty": "#ebedf0",
        "levels": {
            "NONE": "#ebedf0",
            "FIRST_QUARTILE": "#9be9a8",
            "SECOND_QUARTILE": "#40c463",
            "THIRD_QUARTILE": "#30a14e",
            "FOURTH_QUARTILE": "#216e39",
        },
        "blue": "#0969da",
        "blue_text": "#ffffff",
    },
}

WIDTH = 1200
HEIGHT = 265
PANEL_X = 20
PANEL_Y = 54
PANEL_W = 960
PANEL_H = 176
GRID_X = 86
GRID_Y = 95
CELL = 11
GAP = 3
PITCH = CELL + GAP


def graphql() -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required")
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "kanakoy-profile-contribution-renderer",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL HTTP {exc.code}: {detail}") from exc

    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")
    user = payload.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {LOGIN}")
    return user["contributionsCollection"]["contributionCalendar"]


def month_positions(calendar: dict) -> list[tuple[str, int]]:
    weeks = calendar["weeks"]
    positions: list[tuple[str, int]] = []
    last_x = -999
    for month in calendar.get("months", []):
        first_day = date.fromisoformat(month["firstDay"])
        week_index = 0
        found = False
        for idx, week in enumerate(weeks):
            days = [date.fromisoformat(d["date"]) for d in week["contributionDays"]]
            if days and min(days) <= first_day <= max(days):
                week_index = idx
                found = True
                break
            if days and min(days) > first_day:
                week_index = max(0, idx - 1)
                found = True
                break
        if not found:
            week_index = max(0, len(weeks) - 1)
        x = GRID_X + week_index * PITCH
        if x - last_x >= 38:
            positions.append((month["name"][:3], x))
            last_x = x
    return positions


def render(calendar: dict, theme_name: str) -> str:
    t = THEMES[theme_name]
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    current_year = date.today().year
    max_grid_x = GRID_X + max(0, len(weeks) - 1) * PITCH + CELL

    rects: list[str] = []
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            row = int(day["weekday"])
            x = GRID_X + col * PITCH
            y = GRID_Y + row * PITCH
            level = day.get("contributionLevel", "NONE")
            fill = t["levels"].get(level, day.get("color") or t["empty"])
            count = int(day["contributionCount"])
            suffix = "" if count == 1 else "s"
            label = f"{count} contribution{suffix} on {day['date']}"
            rects.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{fill}" data-date="{day["date"]}" data-count="{count}">'
                f'<title>{html.escape(label)}</title></rect>'
            )

    months = "".join(
        f'<text x="{x}" y="82" class="label">{html.escape(name)}</text>'
        for name, x in month_positions(calendar)
    )

    day_labels = (
        f'<text x="46" y="{GRID_Y + PITCH + 9}" class="label">Mon</text>'
        f'<text x="46" y="{GRID_Y + 3 * PITCH + 9}" class="label">Wed</text>'
        f'<text x="46" y="{GRID_Y + 5 * PITCH + 9}" class="label">Fri</text>'
    )

    legend_x = min(780, max_grid_x - 118)
    legend = (
        f'<text x="{legend_x - 34}" y="213" class="muted">Less</text>'
        f'<rect x="{legend_x}" y="204" width="11" height="11" rx="2" fill="{t["empty"]}"/>'
        f'<rect x="{legend_x + 17}" y="204" width="11" height="11" rx="2" fill="{t["levels"]["FIRST_QUARTILE"]}"/>'
        f'<rect x="{legend_x + 34}" y="204" width="11" height="11" rx="2" fill="{t["levels"]["SECOND_QUARTILE"]}"/>'
        f'<rect x="{legend_x + 51}" y="204" width="11" height="11" rx="2" fill="{t["levels"]["THIRD_QUARTILE"]}"/>'
        f'<rect x="{legend_x + 68}" y="204" width="11" height="11" rx="2" fill="{t["levels"]["FOURTH_QUARTILE"]}"/>'
        f'<text x="{legend_x + 86}" y="213" class="muted">More</text>'
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
<title id="title">{total:,} contributions in the last year</title>
<desc id="desc">GitHub contribution calendar for {html.escape(LOGIN)}, generated automatically from the GitHub GraphQL contributionCalendar data.</desc>
<style>
  text {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .title {{ fill:{t["text"]}; font-size:19px; font-weight:400; }}
  .label {{ fill:{t["text"]}; font-size:13px; }}
  .muted {{ fill:{t["muted"]}; font-size:12px; }}
</style>
<rect width="{WIDTH}" height="{HEIGHT}" fill="{t["root"]}"/>
<text x="20" y="32" class="title">{total:,} contributions in the last year</text>
<text x="805" y="31" class="muted">Contribution settings</text>
<path d="M928 25l5 5 5-5" fill="{t["muted"]}"/>
<rect x="1010" y="8" width="160" height="44" rx="7" fill="{t["blue"]}"/>
<text x="1090" y="35" text-anchor="middle" fill="{t["blue_text"]}" font-size="14">{current_year}</text>
<rect x="{PANEL_X}" y="{PANEL_Y}" width="{PANEL_W}" height="{PANEL_H}" rx="7" fill="{t["panel"]}" stroke="{t["border"]}"/>
{months}
{day_labels}
<g>{''.join(rects)}</g>
<a href="https://docs.github.com/en/account-and-profile/reference/profile-contributions-reference">
  <text x="70" y="213" class="muted">Learn how we count contributions</text>
</a>
{legend}
</svg>
'''


def main() -> int:
    calendar = graphql()
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
