#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import random
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

LOGIN = os.environ.get("GITHUB_LOGIN", "Kanakoy-Yokanak")
TOKEN = os.environ.get("CONTRIBUTIONS_TOKEN", "")
DEFENSE_SEED = os.environ.get("DEFENSE_SEED", "")
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
        "ball": "#ff4d67", "paddle0": "#22d3ee", "paddle1": "#39ff88",
    },
    "light": {
        "root0": "#f7fbfe", "root1": "#edf7fb", "panel": "#ffffff",
        "border": "#0891b244", "text": "#0f172a", "muted": "#64748b",
        "cyan": "#0891b2", "green": "#16a34a", "grid": "#0891b2",
        "levels": ["#e8f1f5", "#b7e5d1", "#68cda5", "#2bae72", "#16a34a"],
        "ball": "#e11d48", "paddle0": "#0891b2", "paddle1": "#16a34a",
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
PADDLE_X, PADDLE_W, PADDLE_H = 64, 8, 42
BALL_R = 6
FIELD_TOP, FIELD_BOTTOM = 94, 194


def fetch_calendar() -> dict:
    if not TOKEN:
        raise RuntimeError("CONTRIBUTIONS_TOKEN is required")
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


def seeded_rng(calendar: dict) -> tuple[random.Random, str]:
    fallback = f'{LOGIN}:{calendar["totalContributions"]}:{date.today().isoformat()}'
    seed_text = DEFENSE_SEED or fallback
    rng = random.Random(seed_text)
    short = "".join(ch for ch in seed_text if ch.isalnum())[-8:] or "LOCAL"
    return rng, short.upper()


def game_route(calendar: dict, rng: random.Random) -> tuple[list[int], list[int], list[int]]:
    active: list[tuple[int, int]] = []
    for col, week in enumerate(calendar["weeks"]):
        for day in week["contributionDays"]:
            if int(day["contributionCount"]) <= 0:
                continue
            x = GRID_X + col * PITCH + CELL // 2
            y = GRID_Y + int(day["weekday"]) * PITCH + CELL // 2
            active.append((x, y))

    if active:
        right_edge = max(x for x, _ in active)
        target_pool = [p for p in active if p[0] >= right_edge - 6 * PITCH] or active
    else:
        target_pool = [(1030, 112), (1070, 148), (1010, 182)]

    xs = [PADDLE_X + PADDLE_W + BALL_R + 3]
    ys = [rng.randint(FIELD_TOP + 8, FIELD_BOTTOM - 8)]
    paddle_ys = [max(FIELD_TOP, min(FIELD_BOTTOM - PADDLE_H, ys[0] - PADDLE_H // 2))]

    for _ in range(5):
        tx, ty = rng.choice(target_pool)
        xs.append(max(360, tx - rng.randint(6, 22)))
        ys.append(max(FIELD_TOP + BALL_R, min(FIELD_BOTTOM - BALL_R, ty + rng.randint(-9, 9))))
        rebound_y = rng.randint(FIELD_TOP + BALL_R + 2, FIELD_BOTTOM - BALL_R - 2)
        xs.append(PADDLE_X + PADDLE_W + BALL_R + 3)
        ys.append(rebound_y)
        paddle_ys.append(max(FIELD_TOP, min(FIELD_BOTTOM - PADDLE_H, rebound_y - PADDLE_H // 2)))

    return xs, ys, paddle_ys


def render(calendar: dict, theme_name: str) -> str:
    t = THEMES[theme_name]
    weeks = calendar["weeks"]
    total = int(calendar["totalContributions"])
    rng, seed_label = seeded_rng(calendar)
    xs, ys, paddle_ys = game_route(calendar, rng)
    duration = rng.randint(18, 24)

    ball_x_values = ";".join(map(str, xs))
    ball_y_values = ";".join(map(str, ys))
    ball_key_times = ";".join(f"{i/(len(xs)-1):.4f}" for i in range(len(xs)))
    paddle_values = ";".join(map(str, paddle_ys))
    paddle_outline_values = ";".join(str(v - 3) for v in paddle_ys)
    paddle_key_times = ";".join(f"{i/(len(paddle_ys)-1):.4f}" for i in range(len(paddle_ys)))

    cells: list[str] = []
    active_indices: list[int] = []
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            x = GRID_X + col * PITCH
            y = GRID_Y + int(day["weekday"]) * PITCH
            level = LEVEL_INDEX.get(day["contributionLevel"], 0)
            count = int(day["contributionCount"])
            label = f'{count} contribution{"s" if count != 1 else ""} on {day["date"]}'
            glow = ' filter="url(#cellGlow)"' if level >= 3 else ""
            idx = len(cells)
            if count > 0:
                active_indices.append(idx)
            cells.append(
                f'<rect class="brick" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.2" '
                f'fill="{t["levels"][level]}"{glow} data-date="{day["date"]}" data-count="{count}">'
                f'<title>{html.escape(label)}</title></rect>'
            )

    if active_indices:
        for idx in rng.sample(active_indices, min(8, len(active_indices))):
            delay = rng.uniform(0.2, duration * 0.8)
            pulse = (
                f'<animate attributeName="opacity" values="1;.35;1" dur=".42s" '
                f'begin="{delay:.2f}s;{delay + duration:.2f}s" repeatCount="indefinite"/>'
            )
            cells[idx] = cells[idx].replace("</rect>", pulse + "</rect>")

    months = "".join(
        f'<text x="{x}" y="86" class="month">{html.escape(name)}</text>'
        for name, x in month_positions(calendar)
    )
    max_grid_x = GRID_X + max(0, len(weeks) - 1) * PITCH + CELL
    legend_x = min(1034, max(820, max_grid_x - 4))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
<title id="title">{total:,} contributions in the last year — Brick Defense</title>
<desc id="desc">Horizontal Brick Breaker inspired defense animation over the GitHub contribution field for {html.escape(LOGIN)}. Contribution bricks come from GitHub and the defense route is regenerated from a workflow seed.</desc>
<defs>
  <linearGradient id="rootBg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['root0']}"/><stop offset="1" stop-color="{t['root1']}"/></linearGradient>
  <linearGradient id="frame" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['cyan']}"/><stop offset=".55" stop-color="{t['cyan']}" stop-opacity=".28"/><stop offset="1" stop-color="{t['green']}"/></linearGradient>
  <linearGradient id="paddle" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t['paddle0']}"/><stop offset="1" stop-color="{t['paddle1']}"/></linearGradient>
  <pattern id="microGrid" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M18 0H0V18" fill="none" stroke="{t['grid']}" stroke-width=".45" opacity=".055"/></pattern>
  <filter id="cellGlow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="1.35" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="ballGlow" x="-250%" y="-250%" width="600%" height="600%"><feGaussianBlur stdDeviation="3.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="paddleGlow" x="-300%" y="-80%" width="700%" height="260%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<style>
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
.headline{{fill:{t['text']};font-size:18px;font-weight:700;letter-spacing:.3px}}
.micro{{fill:{t['muted']};font-size:9.5px;letter-spacing:.65px}}
.month{{fill:{t['text']};font-size:11px;font-weight:600;letter-spacing:.4px}}
.day{{fill:{t['muted']};font-size:10px}}
.legend{{fill:{t['muted']};font-size:9.5px;letter-spacing:.5px}}
</style>
<rect width="{WIDTH}" height="{HEIGHT}" rx="16" fill="url(#rootBg)"/>
<rect width="{WIDTH}" height="{HEIGHT}" rx="16" fill="url(#microGrid)"/>
<rect x="1" y="1" width="1198" height="248" rx="15" fill="none" stroke="url(#frame)" stroke-opacity=".62"/>
<circle cx="25" cy="27" r="4.5" fill="#ff5f57"/><circle cx="41" cy="27" r="4.5" fill="#febc2e"/><circle cx="57" cy="27" r="4.5" fill="#28c840"/>
<text x="76" y="31" class="micro">kanakoy@github: ~/contributions</text>
<text x="1170" y="31" text-anchor="end" class="micro">BRICK DEFENSE // SEEDED LIVE LOOP</text>
<text x="28" y="50" class="headline">{total:,} CONTRIBUTIONS // LAST 12 MONTHS</text>
<rect x="{PANEL_X}" y="{PANEL_Y}" width="{PANEL_W}" height="{PANEL_H}" rx="12" fill="{t['panel']}" stroke="{t['border']}"/>
<path d="M42 72h36M42 72v28M1158 72h-36M1158 72v28M42 205h36M42 205v-28M1158 205h-36M1158 205v-28" fill="none" stroke="{t['cyan']}" stroke-width="1.2" opacity=".5"/>
{months}
<text x="54" y="{GRID_Y + PITCH + 8}" class="day">MON</text>
<text x="54" y="{GRID_Y + 3*PITCH + 8}" class="day">WED</text>
<text x="54" y="{GRID_Y + 5*PITCH + 8}" class="day">FRI</text>
<g aria-label="GitHub contribution bricks">{''.join(cells)}</g>
<g aria-label="Horizontal defense paddle">
  <rect x="{PADDLE_X}" y="{paddle_ys[0]}" width="{PADDLE_W}" height="{PADDLE_H}" rx="4" fill="url(#paddle)" filter="url(#paddleGlow)">
    <animate attributeName="y" values="{paddle_values}" keyTimes="{paddle_key_times}" dur="{duration}s" calcMode="linear" repeatCount="indefinite"/>
  </rect>
  <rect x="{PADDLE_X - 2}" y="{paddle_ys[0] - 3}" width="{PADDLE_W + 4}" height="{PADDLE_H + 6}" rx="6" fill="none" stroke="{t['cyan']}" stroke-opacity=".3">
    <animate attributeName="y" values="{paddle_outline_values}" keyTimes="{paddle_key_times}" dur="{duration}s" calcMode="linear" repeatCount="indefinite"/>
  </rect>
</g>
<g aria-label="Defense ball">
  <circle cx="{xs[0]}" cy="{ys[0]}" r="{BALL_R + 6}" fill="{t['ball']}" opacity=".08" filter="url(#ballGlow)">
    <animate attributeName="cx" values="{ball_x_values}" keyTimes="{ball_key_times}" dur="{duration}s" calcMode="linear" repeatCount="indefinite"/>
    <animate attributeName="cy" values="{ball_y_values}" keyTimes="{ball_key_times}" dur="{duration}s" calcMode="linear" repeatCount="indefinite"/>
  </circle>
  <circle cx="{xs[0]}" cy="{ys[0]}" r="{BALL_R}" fill="{t['ball']}" filter="url(#ballGlow)">
    <animate attributeName="cx" values="{ball_x_values}" keyTimes="{ball_key_times}" dur="{duration}s" calcMode="linear" repeatCount="indefinite"/>
    <animate attributeName="cy" values="{ball_y_values}" keyTimes="{ball_key_times}" dur="{duration}s" calcMode="linear" repeatCount="indefinite"/>
  </circle>
</g>
<text x="48" y="210" class="legend">SOURCE // GITHUB CONTRIBUTIONS</text>
<text x="284" y="210" class="legend">DEFENSE SEED // {seed_label}</text>
<text x="{legend_x - 34}" y="210" class="legend">LESS</text>
<rect x="{legend_x}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][0]}"/>
<rect x="{legend_x + 17}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][1]}"/>
<rect x="{legend_x + 34}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][2]}"/>
<rect x="{legend_x + 51}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][3]}" filter="url(#cellGlow)"/>
<rect x="{legend_x + 68}" y="201" width="11" height="11" rx="2.2" fill="{t['levels'][4]}" filter="url(#cellGlow)"/>
<text x="{legend_x + 87}" y="210" class="legend">MORE</text>
</svg>'''


def main() -> int:
    calendar = fetch_calendar()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = OUT_DIR / f"contributions-{theme}.svg"
        path.write_text(render(calendar, theme), encoding="utf-8")
        print(f"wrote {path}")
    print(f"totalContributions={calendar['totalContributions']}")
    print(f"defenseSeed={DEFENSE_SEED or 'daily-fallback'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
