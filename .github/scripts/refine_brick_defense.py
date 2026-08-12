#!/usr/bin/env python3
from __future__ import annotations

import os
import random
import re
from collections import defaultdict
from pathlib import Path

SEED = os.environ.get("DEFENSE_SEED", "local")
ASSETS = (Path("assets/contributions-dark.svg"), Path("assets/contributions-light.svg"))

BALL_COUNT = 3
BALL_RADIUS = 6.0
BALL_HOME_X = 81.0
PADDLE_X = 64.0
PADDLE_W = 8.0
PADDLE_H = 42.0
FIELD_TOP = 94.0
FIELD_BOTTOM = 194.0
PADDLE_MIN_Y = FIELD_TOP
PADDLE_MAX_Y = FIELD_BOTTOM - PADDLE_H
HIT_START = 0.085
HIT_END = 0.785
VICTORY_END = 0.985

BALL_GROUP_RE = re.compile(r'<g aria-label="Defense ball">.*?</g>', re.S)
PADDLE_GROUP_RE = re.compile(r'<g aria-label="Horizontal defense paddle">.*?</g>', re.S)
BRICK_RE = re.compile(
    r'(<rect class="brick" x="(?P<x>-?[0-9.]+)" y="(?P<y>-?[0-9.]+)" '
    r'width="(?P<w>[0-9.]+)" height="(?P<h>[0-9.]+)"(?P<attrs>[^>]*)>)'
    r'(?P<body>.*?)</rect>',
    re.S,
)
OPACITY_ANIM_RE = re.compile(r'<animate attributeName="opacity"[^>]*/>')


def fmt(value: float) -> str:
    text = f"{value:.3f}"
    return text.rstrip("0").rstrip(".")


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def collect_active_bricks(svg: str) -> list[dict[str, float | int]]:
    bricks: list[dict[str, float | int]] = []
    for match in BRICK_RE.finditer(svg):
        attrs = match.group("attrs")
        count_match = re.search(r'data-count="([0-9]+)"', attrs)
        count = int(count_match.group(1)) if count_match else 0
        if count <= 0:
            continue

        x = float(match.group("x"))
        y = float(match.group("y"))
        w = float(match.group("w"))
        h = float(match.group("h"))
        bricks.append(
            {
                "start": match.start(),
                "left_x": x,
                "center_x": x + w / 2,
                "center_y": y + h / 2,
                "count": count,
            }
        )
    return bricks


def frontline_order(bricks: list[dict[str, float | int]], rng: random.Random) -> list[dict[str, float | int]]:
    """Return every active brick in strict exposed-front order.

    Columns are always cleared from left to right. Only the order inside one
    exposed column is allowed to vary with the workflow seed.
    """
    columns: dict[float, list[dict[str, float | int]]] = defaultdict(list)
    for brick in bricks:
        columns[float(brick["left_x"])].append(brick)

    ordered: list[dict[str, float | int]] = []
    for x in sorted(columns):
        column = list(columns[x])
        rng.shuffle(column)
        ordered.extend(column)
    return ordered


def cycle_duration(active_count: int) -> float:
    # Long enough for three balls to clear dense fields without becoming a
    # frantic strobe. Caps keep the profile animation from turning into a film.
    return clamp(18.0 + active_count * 0.68, 38.0, 92.0)


def build_hit_schedule(
    ordered: list[dict[str, float | int]],
) -> list[dict[str, float | int]]:
    if not ordered:
        return []

    # Add a little extra temporal weight when advancing to the next column so
    # the viewer can perceive the frontline peeling away layer by layer.
    weights: list[float] = []
    previous_x: float | None = None
    for brick in ordered:
        x = float(brick["left_x"])
        weight = 1.0
        if previous_x is not None and abs(x - previous_x) > 0.01:
            weight += 0.55
        weights.append(weight)
        previous_x = x

    total_weight = sum(weights)
    cumulative = 0.0
    schedule: list[dict[str, float | int]] = []
    for index, (brick, weight) in enumerate(zip(ordered, weights)):
        midpoint = cumulative + weight * 0.5
        frac = HIT_START + (HIT_END - HIT_START) * (midpoint / total_weight)
        event = dict(brick)
        event["frac"] = frac
        event["ball"] = index % BALL_COUNT
        schedule.append(event)
        cumulative += weight
    return schedule


def build_ball_tracks(
    schedule: list[dict[str, float | int]],
    rng: random.Random,
) -> tuple[list[dict[str, str]], list[tuple[float, float]]]:
    per_ball: list[list[dict[str, float | int]]] = [[] for _ in range(BALL_COUNT)]
    for event in schedule:
        per_ball[int(event["ball"])].append(event)

    tracks: list[dict[str, str]] = []
    paddle_events: list[tuple[float, float]] = []

    for ball_id, events in enumerate(per_ball):
        base_y = clamp(112.0 + ball_id * 27.0 + rng.uniform(-5.0, 5.0), FIELD_TOP + 7, FIELD_BOTTOM - 7)
        points: list[tuple[float, float, float]] = [(0.0, BALL_HOME_X, base_y)]

        for idx, event in enumerate(events):
            frac = float(event["frac"])
            prev_frac = float(events[idx - 1]["frac"]) if idx else 0.0
            next_frac = float(events[idx + 1]["frac"]) if idx + 1 < len(events) else 1.0
            safe_gap = min(frac - prev_frac, next_frac - frac)
            travel = clamp(safe_gap * 0.31, 0.0085, 0.021)

            launch_t = max(points[-1][0] + 0.001, frac - travel)
            return_t = min(frac + travel, next_frac - 0.001 if idx + 1 < len(events) else 0.91)
            if return_t <= frac:
                return_t = min(0.91, frac + 0.006)

            target_y = float(event["center_y"])
            launch_y = clamp(target_y + rng.uniform(-31.0, 31.0), FIELD_TOP + 7, FIELD_BOTTOM - 7)
            return_y = clamp(target_y + rng.uniform(-29.0, 29.0), FIELD_TOP + 7, FIELD_BOTTOM - 7)
            target_x = float(event["left_x"]) - BALL_RADIUS

            if launch_t > points[-1][0]:
                points.append((launch_t, BALL_HOME_X, launch_y))
            points.append((frac, target_x, target_y))
            points.append((return_t, BALL_HOME_X, return_y))

            paddle_events.append((launch_t, launch_y - PADDLE_H / 2))
            paddle_events.append((return_t, return_y - PADDLE_H / 2))

        end_y = points[-1][2] if points else base_y
        if points[-1][0] < 1.0:
            points.append((1.0, BALL_HOME_X, end_y))

        # Remove pathological duplicate times while preserving the last point.
        compact: list[tuple[float, float, float]] = []
        for point in points:
            if compact and abs(point[0] - compact[-1][0]) < 0.0005:
                compact[-1] = point
            else:
                compact.append(point)

        tracks.append(
            {
                "x": ";".join(fmt(point[1]) for point in compact),
                "y": ";".join(fmt(point[2]) for point in compact),
                "times": ";".join(f"{point[0]:.4f}" for point in compact),
            }
        )

    return tracks, paddle_events


def replace_multiball(svg: str, tracks: list[dict[str, str]], duration: float, ball_color: str) -> str:
    groups: list[str] = []
    for index, track in enumerate(tracks, start=1):
        x0 = track["x"].split(";")[0]
        y0 = track["y"].split(";")[0]
        phase_opacity = 0.075 + (index - 1) * 0.012
        groups.append(
            f'<g aria-label="Defense ball {index} of {BALL_COUNT}">'
            f'<circle cx="{x0}" cy="{y0}" r="12" fill="{ball_color}" opacity="{phase_opacity:.3f}" filter="url(#ballGlow)">'
            f'<animate attributeName="cx" values="{track["x"]}" keyTimes="{track["times"]}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{track["y"]}" keyTimes="{track["times"]}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
            f'</circle>'
            f'<circle cx="{x0}" cy="{y0}" r="{fmt(BALL_RADIUS)}" fill="{ball_color}" filter="url(#ballGlow)">'
            f'<animate attributeName="cx" values="{track["x"]}" keyTimes="{track["times"]}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{track["y"]}" keyTimes="{track["times"]}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
            f'</circle>'
            f'</g>'
        )

    replacement = '<g aria-label="Defense multiball x3">' + "".join(groups) + '</g>'
    svg, count = BALL_GROUP_RE.subn(replacement, svg, count=1)
    if count != 1:
        raise RuntimeError("original defense ball group not found")
    return svg


def inject_brick_destruction(
    svg: str,
    schedule: list[dict[str, float | int]],
    duration: float,
) -> str:
    hit_by_start = {int(event["start"]): float(event["frac"]) for event in schedule}

    def replace(match: re.Match[str]) -> str:
        frac = hit_by_start.get(match.start())
        if frac is None:
            return match.group(0)

        # Remove the old decorative pulse. A brick that is being destroyed gets
        # one authoritative opacity timeline instead of competing animations.
        body = OPACITY_ANIM_RE.sub("", match.group("body"))
        pre = max(0.0, frac - 0.006)
        flash = min(0.994, frac + 0.007)
        gone = min(0.997, frac + 0.020)
        anim = (
            f'<animate attributeName="opacity" values="1;1;.2;0;0" '
            f'keyTimes="0;{pre:.4f};{flash:.4f};{gone:.4f};1" '
            f'dur="{fmt(duration)}s" repeatCount="indefinite"/>'
        )
        return f'{match.group(1)}{body}{anim}</rect>'

    return BRICK_RE.sub(replace, svg)


def inject_hit_sparks(
    svg: str,
    schedule: list[dict[str, float | int]],
    duration: float,
    ball_color: str,
) -> str:
    sparks: list[str] = []
    for event in schedule:
        frac = float(event["frac"])
        x = float(event["center_x"])
        y = float(event["center_y"])
        start = max(0.0, frac - 0.004)
        peak = min(0.992, frac + 0.008)
        end = min(0.997, frac + 0.030)
        sparks.append(
            f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="2.2" fill="{ball_color}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;.92;0;0" '
            f'keyTimes="0;{start:.4f};{peak:.4f};{end:.4f};1" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="r" values="2.2;2.2;8;15;15" '
            f'keyTimes="0;{start:.4f};{peak:.4f};{end:.4f};1" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'</circle>'
        )

    if not sparks:
        return svg
    marker = '<g aria-label="Defense multiball x3">'
    return svg.replace(marker, '<g aria-label="Brick impact sparks">' + "".join(sparks) + '</g>\n' + marker, 1)


def build_paddle_track(
    paddle_events: list[tuple[float, float]],
    rng: random.Random,
) -> tuple[list[float], list[float]]:
    if not paddle_events:
        return [112.0, 126.0, 105.0, 112.0], [0.0, 0.34, 0.68, 1.0]

    paddle_events = sorted(paddle_events)
    sample_count = 25
    values: list[float] = []
    times: list[float] = []
    previous = clamp(paddle_events[0][1], PADDLE_MIN_Y, PADDLE_MAX_Y)

    for index in range(sample_count):
        t = index / (sample_count - 1)
        nearby = [
            y for event_t, y in paddle_events
            if abs(event_t - t) <= 0.055
        ]
        if nearby:
            target = sum(nearby) / len(nearby)
        else:
            _, target = min(paddle_events, key=lambda item: abs(item[0] - t))

        # Human-like controller behavior: lag behind the mathematical target,
        # then make small deterministic corrections instead of snapping.
        blended = previous * 0.48 + target * 0.52 + rng.uniform(-2.3, 2.3)
        current = clamp(blended, PADDLE_MIN_Y, PADDLE_MAX_Y)
        values.append(current)
        times.append(t)
        previous = current

    values[-1] = values[0]
    return values, times


def replace_paddle(
    svg: str,
    values: list[float],
    times: list[float],
    duration: float,
) -> str:
    value_text = ";".join(fmt(value) for value in values)
    outline_text = ";".join(fmt(value - 3) for value in values)
    time_text = ";".join(f"{value:.4f}" for value in times)
    splines = ";".join("0.22 0.61 0.36 1" for _ in range(len(values) - 1))

    replacement = (
        '<g aria-label="Horizontal defense paddle">'
        f'<rect x="{fmt(PADDLE_X)}" y="{fmt(values[0])}" width="{fmt(PADDLE_W)}" height="{fmt(PADDLE_H)}" rx="4" fill="url(#paddle)" filter="url(#paddleGlow)">'
        f'<animate attributeName="y" values="{value_text}" keyTimes="{time_text}" keySplines="{splines}" '
        f'dur="{fmt(duration)}s" calcMode="spline" repeatCount="indefinite"/>'
        '</rect>'
        f'<rect x="{fmt(PADDLE_X - 2)}" y="{fmt(values[0] - 3)}" width="{fmt(PADDLE_W + 4)}" height="{fmt(PADDLE_H + 6)}" rx="6" fill="none" stroke="url(#frame)" stroke-opacity=".42">'
        f'<animate attributeName="y" values="{outline_text}" keyTimes="{time_text}" keySplines="{splines}" '
        f'dur="{fmt(duration)}s" calcMode="spline" repeatCount="indefinite"/>'
        '</rect>'
        '</g>'
    )

    svg, count = PADDLE_GROUP_RE.subn(replacement, svg, count=1)
    if count != 1:
        raise RuntimeError("paddle group not found")
    return svg


def inject_victory(
    svg: str,
    schedule: list[dict[str, float | int]],
    duration: float,
    theme: str,
) -> str:
    if not schedule:
        return svg

    last_hit = max(float(event["frac"]) for event in schedule)
    appear = min(0.90, last_hit + 0.028)
    full = min(0.93, appear + 0.025)
    fade = VICTORY_END
    panel_fill = "#07131cf0" if theme == "dark" else "#fffffff2"
    text = "#f0f6fc" if theme == "dark" else "#0f172a"
    muted = "#7f95a9" if theme == "dark" else "#64748b"
    green = "#39ff88" if theme == "dark" else "#16a34a"
    cyan = "#22d3ee" if theme == "dark" else "#0891b2"

    victory = (
        '<g aria-label="Field clear congratulations" opacity="0">'
        f'<animate attributeName="opacity" values="0;0;1;1;0" '
        f'keyTimes="0;{appear:.4f};{full:.4f};{fade:.4f};1" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
        f'<rect x="318" y="104" width="564" height="76" rx="14" fill="{panel_fill}" stroke="{green}" stroke-width="1.4"/>'
        f'<rect x="329" y="114" width="542" height="56" rx="10" fill="none" stroke="{cyan}" stroke-opacity=".36"/>'
        f'<text x="600" y="139" text-anchor="middle" fill="{green}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="18" font-weight="700" letter-spacing="1.2">CONGRATULATIONS // FIELD CLEARED</text>'
        f'<text x="600" y="160" text-anchor="middle" fill="{text}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10.5" letter-spacing=".85">100% CONTRIBUTION BRICKS DESTROYED // MULTIBALL x{BALL_COUNT}</text>'
        f'<circle cx="350" cy="142" r="3.5" fill="{green}"/><circle cx="850" cy="142" r="3.5" fill="{green}"/>'
        f'<text x="600" y="174" text-anchor="middle" fill="{muted}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="8.5" letter-spacing=".55">NEXT ROUND INITIALIZING</text>'
        '</g>'
    )

    marker = '<text x="48" y="210" class="legend">SOURCE // GITHUB CONTRIBUTIONS</text>'
    if marker not in svg:
        raise RuntimeError("legend marker not found for victory insertion")
    return svg.replace(marker, victory + "\n" + marker, 1)


def refine(path: Path) -> None:
    svg = path.read_text(encoding="utf-8")
    theme = "dark" if "dark" in path.name else "light"
    ball_color = "#ff4d67" if theme == "dark" else "#e11d48"

    rng = random.Random(f"{SEED}:{theme}:multiball")
    bricks = collect_active_bricks(svg)
    ordered = frontline_order(bricks, rng)
    schedule = build_hit_schedule(ordered)
    duration = cycle_duration(len(ordered))

    tracks, paddle_events = build_ball_tracks(schedule, rng)
    paddle_values, paddle_times = build_paddle_track(paddle_events, random.Random(f"{SEED}:{theme}:paddle"))

    svg = inject_brick_destruction(svg, schedule, duration)
    svg = replace_multiball(svg, tracks, duration, ball_color)
    svg = inject_hit_sparks(svg, schedule, duration, ball_color)
    svg = replace_paddle(svg, paddle_values, paddle_times, duration)
    svg = inject_victory(svg, schedule, duration, theme)

    svg = svg.replace(
        "BRICK DEFENSE // SEEDED LIVE LOOP",
        f"BRICK DEFENSE // MULTIBALL x{BALL_COUNT} // 100% CLEAR",
        1,
    )
    svg = svg.replace(
        "Contribution bricks come from GitHub and the defense route is regenerated from a workflow seed.",
        f"Three red defense balls clear every active contribution brick from the exposed frontline before a synchronized congratulations state.",
        1,
    )

    path.write_text(svg, encoding="utf-8")
    final_hit = max((float(event["frac"]) for event in schedule), default=0.0)
    print(
        f"refined {path}: active_bricks={len(bricks)} cleared={len(schedule)} "
        f"balls={BALL_COUNT} duration={fmt(duration)}s final_hit={final_hit:.4f}"
    )


def main() -> int:
    for path in ASSETS:
        refine(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
