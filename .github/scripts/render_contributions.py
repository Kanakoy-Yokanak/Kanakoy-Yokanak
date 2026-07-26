#!/usr/bin/env python3
# Render a GitHub-native-looking contribution calendar from the user's public profile.

from __future__ import annotations

import html
import os
import re
import sys
import urllib.request
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path

LOGIN = os.environ.get("GITHUB_LOGIN", "Kanakoy-Yokanak")
OUT_DIR = Path("assets")
PUBLIC_URL = f"https://github.com/users/{LOGIN}/contributions"

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

WIDTH, HEIGHT = 1200, 265
GRID_X, GRID_Y = 86, 95
CELL, PITCH = 11, 14


class ContributionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.days: dict[str, dict] = {}
        self.day_id_to_date: dict[str, str] = {}
        self.tooltip_for: str | None = None
        self.tooltip_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        data = dict(attrs)
        if tag == "td":
            classes = data.get("class", "")
            if "ContributionCalendar-day" in classes and data.get("data-date"):
                dt = data["data-date"]
                level = int(data.get("data-level", "0") or 0)
                day_id = data.get("id", "")
                self.days[dt] = {"date": dt, "level": max(0, min(4, level)), "count": 0}
                if day_id:
                    self.day_id_to_date[day_id] = dt
        elif tag == "tool-tip":
            self.tooltip_for = data.get("for")
            self.tooltip_text = []

    def handle_data(self, data: str) -> None:
        if self.tooltip_for:
            self.tooltip_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "tool-tip" or not self.tooltip_for:
            return
        dt = self.day_id_to_date.get(self.tooltip_for)
        if dt and dt in self.days:
            text = " ".join("".join(self.tooltip_text).split())
            m = re.search(r"\b(\d[\d,]*)\s+contribution", text, re.I)
            if m:
                self.days[dt]["count"] = int(m.group(1).replace(",", ""))
            elif re.search(r"\bNo\s+contributions?\b", text, re.I):
                self.days[dt]["count"] = 0
        self.tooltip_for = None
        self.tooltip_text = []


def fetch_public_calendar() -> dict:
    req = urllib.request.Request(
        PUBLIC_URL,
        headers={
            "User-Agent": "Mozilla/5.0 kanakoy-profile-contribution-renderer",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        source = response.read().decode("utf-8", errors="replace")

    parser = ContributionParser()
    parser.feed(source)
    if not parser.days:
        raise RuntimeError("GitHub contribution table was not found in the public profile response")

    total_match = re.search(
        r"([\d,]+)\s+contributions?\s+in\s+the\s+last\s+year",
        source,
        re.I | re.S,
    )
    total = int(total_match.group(1).replace(",", "")) if total_match else sum(
        day["count"] for day in parser.days.values()
    )

    dates = sorted(date.fromisoformat(value) for value in parser.days)
    first, last = dates[0], dates[-1]
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)
    grid_end = last + timedelta(days=(6 - ((last.weekday() + 1) % 7)))
    week_count = ((grid_end - grid_start).days // 7) + 1

    weeks = []
    for col in range(week_count):
        sunday = grid_start + timedelta(days=col * 7)
        week_days = []
        for row in range(7):
            dt = sunday + timedelta(days=row)
            item = parser.days.get(dt.isoformat(), {"date": dt.isoformat(), "level": 0, "count": 0})
            week_days.append({**item, "weekday": row})
        weeks.append({"firstDay": sunday.isoformat(), "contributionDays": week_days})

    months = []
    seen = set()
    for dt in dates:
        key = (dt.year, dt.month)
        if key in seen:
            continue
        seen.add(key)
        months.append({"name": dt.strftime("%b"), "firstDay": date(dt.year, dt.month, 1).isoformat()})

    return {"totalContributions": total, "weeks": weeks, "months": months, "lastDate": last.isoformat()}


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
            out.append((month["name"], x))
            last_x = x
    return out


def render(calendar: dict, theme_name: str) -> str:
    t = THEMES[theme_name]
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    year = date.fromisoformat(calendar["lastDate"]).year

    cells = []
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            x = GRID_X + col * PITCH
            y = GRID_Y + int(day["weekday"]) * PITCH
            level = max(0, min(4, int(day["level"])))
            count = int(day["count"])
            label = f'{count} contribution{"s" if count != 1 else ""} on {day["date"]}'
            cells.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{t["levels"][level]}" '
                f'data-date="{day["date"]}" data-level="{level}" data-count="{count}">'
                f'<title>{html.escape(label)}</title></rect>'
            )

    months = "".join(
        f'<text x="{x}" y="82" class="label">{html.escape(name)}</text>'
        for name, x in month_positions(calendar)
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
<title id="title">{total:,} contributions in the last year</title>
<desc id="desc">Live public GitHub contribution calendar for {html.escape(LOGIN)}.</desc>
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
    calendar = fetch_public_calendar()
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
