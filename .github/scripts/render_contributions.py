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
        "root0": "#061019", "root1": "#091720", "panel": "#07131c",
        "border": "#22d3ee55", "text": "#f0f6fc", "muted": "#7f95a9",
        "cyan": "#22d3ee", "green": "#39ff88", "grid": "#22d3ee",
        "levels": ["#0b1822", "#104539", "#0b7959", "#17b978", "#39ff88"],
    },
    "light": {
        "root0": "#f7fbfe", "root1": "#edf7fb", "panel": "#ffffff",
        "border": "#0891b244", "text": "#0f172a", "muted": "#64748b",
        "cyan": "#0891b2", "green": "#16a34a", "grid": "#0891b2",
        "levels": ["#e8f1f5", "#b7e5d1", "#68cda5", "#2bae72", "#16a34a"],
    },
}

LEVEL_INDEX = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

WIDTH, HEIGHT = 1200, 250
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 26, 55, 1148, 166
GRID_X, GRID_Y = 92, 99
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
    out: list[tuple[str, int]] = []
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
            out.append((month["name"][:3].upper(), x))
            last_x = x
    return out


def render(calendar: dict, theme_name: str) -> str:
    t = THEMES[theme_name]
    weeks = calendar["weeks"]
    total = int(calendar["totalContributions"])

    cells: list[str] = []
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            x = GRID_X + col * PITCH
            y = GRID_Y + int(day["weekday"]) * PITCH
            level = LEVEL_INDEX.get(day["contributionLevel"], 0)
            count = int(day["contributionCount"])
            delay = min(2.25, col * 0.025 + int(day["weekday"]) * 0.01)
            label = f'{count} contribution{"s" if count != 1 else ""} on {day["date"]}'
            glow = ' filter="url(#cellGlow)"' if level >= 3 else ""
            cells.append(
                f'<rect class="cell" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.2" '
                f'fill="{t["levels"][level]}" style="animation-delay:{delay:.2f}s"{glow} '
                f'data-date="{day["date"]}" data-count="{count}"><title>{html.escape(label)}</title></rect>'
            )

    months = "".join(
        f'<text x="{x}" y="86" class="month">{html.escape(name)}</text>'
        for name, x in month_positions(calendar)
    )

    max_grid_x = GRID_X + max(0, len(weeks) - 1) * PITCH + CELL
    legend_x = min(1034, max(820, max_grid_x - 4))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
<title id="title">{total:,} contributions in the last year</title>
<desc id="desc">Cyber styled GitHub contribution calendar for {html.escape(LOGIN)}, generated automatically from GitHub contribution data.</desc>
<defs>
  <linearGradient id="rootBg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['root0']}"/><stop offset="1" stop-color="{t['root1']}"/></linearGradient>
  <linearGradient id="frame" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['cyan']}"/><stop offset=".55" stop-color="{t['cyan']}" stop-opacity=".28"/><stop offset="1" stop-color="{t['green']}"/></linearGradient>
  <linearGradient id="scan" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t['cyan']}" stop-opacity="0"/><stop offset=".5" stop-color="{t['cyan']}" stop-opacity=".42"/><stop offset="1" stop-color="{t['green']}" stop-opacity="0"/></linearGradient>
  <pattern id="microGrid" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M18 0H0V18" fill="none" stroke="{t['grid']}" stroke-width=".45" opacity=".055"/></pattern>
  <filter id="cellGlow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="1.35" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<style>
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
.headline{{fill:{t['text']};font-size:18px;font-weight:700;letter-spacing:.3px}}
.micro{{fill:{t['muted']};font-size:9.5px;letter-spacing:.65px}}
.month{{fill:{t['text']};font-size:11px;font-weight:600;letter-spacing:.4px}}
.day{{fill:{t['muted']};font-size:10px}}
.legend{{fill:{t['muted']};font-size:9.5px;letter-spacing:.5px}}
.cell{{opacity:0;animation:cellIn .42s ease forwards;transform-box:fill-box;transform-origin:center}}
@keyframes cellIn{{from{{opacity:0;transform:translateY(-3px) scale(.72)}}to{{opacity:1;transform:translateY(0) scale(1)}}}}
</style>
<rect width="{WIDTH}" height="{HEIGHT}" rx="16" fill="url(#rootBg)"/>
<rect width="{WIDTH}" height="{HEIGHT}" rx="16" fill="url(#microGrid)"/>
<rect x="1" y="1" width="1198" height="248" rx="15" fill="none" stroke="url(#frame)" stroke-opacity=".62"/>
<circle cx="25" cy="27" r="4.5" fill="#ff5f57"/><circle cx="41" cy="27" r="4.5" fill="#febc2e"/><circle cx="57" cy="27" r="4.5" fill="#28c840"/>
<text x="76" y="31" class="micro">kanakoy@github: ~/contributions</text>
<text x="1170" y="31" text-anchor="end" class="micro">ACTIVITY STREAM // LIVE SOURCE</text>
<text x="28" y="50" class="headline">{total:,} CONTRIBUTIONS // LAST 12 MONTHS</text>
<rect x="{PANEL_X}" y="{PANEL_Y}" width="{PANEL_W}" height="{PANEL_H}" rx="12" fill="{t['panel']}" stroke="{t['border']}"/>
<path d="M42 72h36M42 72v28M1158 72h-36M1158 72v28M42 205h36M42 205v-28M1158 205h-36M1158 205v-28" fill="none" stroke="{t['cyan']}" stroke-width="1.2" opacity=".5"/>
{months}
<text x="54" y="{GRID_Y + PITCH + 8}" class="day">MON</text>
<text x="54" y="{GRID_Y + 3*PITCH + 8}" class="day">WED</text>
<text x="54" y="{GRID_Y + 5*PITCH + 8}" class="day">FRI</text>
<g>{''.join(cells)}</g>
<text x="48" y="210" class="legend">SOURCE // GITHUB CONTRIBUTIONS</text>
<text x="{legend_x - 34}" y="210" class="legend">LESS</text>
<rect x="{legend_x}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][0]}"/>
<rect x="{legend_x + 17}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][1]}"/>
<rect x="{legend_x + 34}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][2]}"/>
<rect x="{legend_x + 51}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][3]}" filter="url(#cellGlow)"/>
<rect x="{legend_x + 68}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][4]}" filter="url(#cellGlow)"/>
<text x="{legend_x + 87}" y="210" class="legend">MORE</text>
<rect x="28" y="58" width="1144" height="18" fill="url(#scan)" opacity="0"><animate attributeName="y" values="58;197;58" dur="8s" begin="1.2s" repeatCount="indefinite"/><animate attributeName="opacity" values="0;.7;0" dur="8s" begin="1.2s" repeatCount="indefinite"/></rect>
</svg>'''


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
