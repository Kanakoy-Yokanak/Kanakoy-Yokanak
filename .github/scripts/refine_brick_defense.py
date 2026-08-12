#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import random
import re
from collections import defaultdict
from pathlib import Path

SEED = os.environ.get("DEFENSE_SEED", "local")
ASSETS = (Path("assets/contributions-dark.svg"), Path("assets/contributions-light.svg"))

BALL_RADIUS = 6.0
BALL_HOME_X = 81.0
PADDLE_X = 64.0
PADDLE_W = 8.0
PADDLE_H = 42.0
FIELD_TOP = 94.0
FIELD_BOTTOM = 194.0
HIT_END = 0.795
VICTORY_APPEAR_PAD = 0.030
VICTORY_END = 0.985
BASE_SPEED_PX_S = 1050.0
SPEED_STEP = 0.055
MAX_SPEED_MULTIPLIER = 3.6

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
    """Return only contribution cells that actually exist and are live targets."""
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


def frontline_order(
    bricks: list[dict[str, float | int]],
    rng: random.Random,
) -> list[dict[str, float | int]]:
    """Destroy every real brick once, exposed column first, left to right."""
    columns: dict[float, list[dict[str, float | int]]] = defaultdict(list)
    for brick in bricks:
        columns[float(brick["left_x"])].append(brick)

    ordered: list[dict[str, float | int]] = []
    for x in sorted(columns):
        column = list(columns[x])
        rng.shuffle(column)
        ordered.extend(column)
    return ordered


def speed_multiplier(destroyed: int) -> float:
    """Speed increases immediately after each destroyed contribution brick."""
    return min(MAX_SPEED_MULTIPLIER, 1.0 + destroyed * SPEED_STEP)


def paddle_center(t: float, phase: float) -> float:
    """Fluid defense motion. Exact ball catches use this same curve."""
    center_min = FIELD_TOP + PADDLE_H / 2 + 2
    center_max = FIELD_BOTTOM - PADDLE_H / 2 - 2
    raw = (
        144.0
        + 27.0 * math.sin(2 * math.pi * (1.75 * t + phase))
        + 9.0 * math.sin(2 * math.pi * (4.15 * t + phase * 0.37))
        + 3.5 * math.sin(2 * math.pi * (7.20 * t + phase * 0.13))
    )
    return clamp(raw, center_min, center_max)


def build_single_ball_round(
    ordered: list[dict[str, float | int]],
    phase: float,
) -> tuple[
    list[tuple[float, float, float]],
    list[dict[str, float | int]],
    list[float],
    float,
]:
    """Create one continuous ball path that only visits real live bricks.

    Sequence is always:
      paddle -> live brick -> paddle -> next live brick -> ... -> zero bricks.

    There are no roaming or synthetic targets, so the ball can never hit an
    invisible or non-existent grid cell. Travel time shrinks after every hit.
    """
    if not ordered:
        y = paddle_center(0.0, phase)
        return [(0.0, BALL_HOME_X, y), (1.0, 410.0, y)], [], [0.0], 12.0

    raw_events: list[dict[str, float | int]] = []
    raw_points: list[tuple[float, str, float, float]] = []
    raw_catches: list[float] = [0.0]
    cursor_s = 0.0
    raw_points.append((0.0, "paddle", BALL_HOME_X, 0.0))

    for index, brick in enumerate(ordered):
        target_x = float(brick["left_x"]) - BALL_RADIUS
        target_y = float(brick["center_y"])

        outbound_speed = BASE_SPEED_PX_S * speed_multiplier(index)
        cursor_s += abs(target_x - BALL_HOME_X) / outbound_speed

        event = dict(brick)
        event["seconds"] = cursor_s
        event["index"] = index
        event["speed_mult"] = speed_multiplier(index)
        raw_events.append(event)
        raw_points.append((cursor_s, "hit", target_x, target_y))

        if index == len(ordered) - 1:
            break

        return_speed = BASE_SPEED_PX_S * speed_multiplier(index + 1)
        cursor_s += abs(target_x - BALL_HOME_X) / return_speed
        raw_catches.append(cursor_s)
        raw_points.append((cursor_s, "paddle", BALL_HOME_X, 0.0))

    duration = max(10.0, cursor_s / HIT_END)

    schedule: list[dict[str, float | int]] = []
    for event in raw_events:
        item = dict(event)
        item["frac"] = float(event["seconds"]) / duration
        schedule.append(item)

    catch_fracs = [seconds / duration for seconds in raw_catches]
    points: list[tuple[float, float, float]] = []
    for seconds, kind, x, y in raw_points:
        frac = seconds / duration
        if kind == "paddle":
            y = paddle_center(frac, phase)
        points.append((frac, x, y))

    final_t, final_x, final_y = points[-1]
    hold_t = min(0.94, final_t + 0.018)
    if hold_t > final_t:
        points.append((hold_t, final_x, final_y))
    points.append((1.0, final_x, final_y))

    return points, schedule, catch_fracs, duration


def compact_path(points: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    points = sorted(points, key=lambda point: point[0])
    compact: list[tuple[float, float, float]] = []
    for point in points:
        if compact and abs(point[0] - compact[-1][0]) < 0.00035:
            compact[-1] = point
        else:
            compact.append(point)
    if compact[0][0] != 0.0:
        compact.insert(0, (0.0, compact[0][1], compact[0][2]))
    if compact[-1][0] < 1.0:
        compact.append((1.0, compact[-1][1], compact[-1][2]))
    return compact


def replace_single_ball(
    svg: str,
    raw_path: list[tuple[float, float, float]],
    schedule: list[dict[str, float | int]],
    duration: float,
    ball_color: str,
) -> str:
    path = compact_path(raw_path)
    fade_start = min(
        0.94,
        (float(schedule[-1]["frac"]) + VICTORY_APPEAR_PAD) if schedule else 0.88,
    )
    fade_end = min(0.975, fade_start + 0.022)

    x_values = ";".join(fmt(point[1]) for point in path)
    y_values = ";".join(fmt(point[2]) for point in path)
    key_times = ";".join(f"{point[0]:.4f}" for point in path)
    x0, y0 = path[0][1], path[0][2]

    replacement = (
        '<g aria-label="Defense accelerating single ball">'
        f'<animate attributeName="opacity" values="1;1;0;0" '
        f'keyTimes="0;{fade_start:.4f};{fade_end:.4f};1" '
        f'dur="{fmt(duration)}s" repeatCount="indefinite"/>'
        f'<circle cx="{fmt(x0)}" cy="{fmt(y0)}" r="11" fill="{ball_color}" opacity=".075" filter="url(#ballGlow)">'
        f'<animate attributeName="cx" values="{x_values}" keyTimes="{key_times}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
        f'<animate attributeName="cy" values="{y_values}" keyTimes="{key_times}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
        '</circle>'
        f'<circle cx="{fmt(x0)}" cy="{fmt(y0)}" r="{fmt(BALL_RADIUS)}" fill="{ball_color}" filter="url(#ballGlow)">'
        f'<animate attributeName="cx" values="{x_values}" keyTimes="{key_times}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
        f'<animate attributeName="cy" values="{y_values}" keyTimes="{key_times}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
        '</circle>'
        '</g>'
    )
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

        body = OPACITY_ANIM_RE.sub("", match.group("body"))
        pre = max(0.0, frac - 0.004)
        flash = min(0.994, frac + 0.004)
        gone = min(0.997, frac + 0.012)
        anim = (
            f'<animate attributeName="opacity" values="1;1;.12;0;0" '
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
        start = max(0.0, frac - 0.002)
        peak = min(0.992, frac + 0.005)
        end = min(0.997, frac + 0.018)
        sparks.append(
            f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="2" fill="{ball_color}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;.88;0;0" '
            f'keyTimes="0;{start:.4f};{peak:.4f};{end:.4f};1" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="r" values="2;2;6.5;11;11" '
            f'keyTimes="0;{start:.4f};{peak:.4f};{end:.4f};1" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            '</circle>'
        )

    if not sparks:
        return svg
    marker = '<g aria-label="Defense accelerating single ball">'
    index = svg.find(marker)
    if index < 0:
        raise RuntimeError("single ball marker not found")
    insertion = '<g aria-label="Brick impact sparks">' + "".join(sparks) + '</g>\n'
    return svg[:index] + insertion + svg[index:]


def replace_live_paddle(
    svg: str,
    catch_times: list[float],
    phase: float,
    duration: float,
) -> str:
    times = {i / 72 for i in range(73)}
    times.update(t for t in catch_times if 0.0 <= t <= 0.94)
    times.add(0.0)
    times.add(1.0)
    ordered_times = sorted(times)

    values = [paddle_center(t, phase) - PADDLE_H / 2 for t in ordered_times]
    value_text = ";".join(fmt(value) for value in values)
    outline_text = ";".join(fmt(value - 3) for value in values)
    time_text = ";".join(f"{t:.4f}" for t in ordered_times)
    splines = ";".join("0.25 0.10 0.25 1" for _ in range(len(ordered_times) - 1))

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


def inject_status_counter(
    svg: str,
    schedule: list[dict[str, float | int]],
    duration: float,
    theme: str,
) -> str:
    if not schedule:
        return svg

    accent = "#ff6b80" if theme == "dark" else "#be123c"
    muted = "#7f95a9" if theme == "dark" else "#64748b"
    groups: list[str] = []
    total = len(schedule)
    starts = [0.0] + [min(0.97, float(event["frac"]) + 0.002) for event in schedule]

    for destroyed in range(0, total + 1):
        start = starts[destroyed]
        end = starts[destroyed + 1] if destroyed < total else 1.0
        remaining = total - destroyed
        speed = speed_multiplier(destroyed)

        if destroyed == 0:
            opacity_values = "1;1;0;0"
            opacity_times = f"0;{max(0.001, end - 0.001):.4f};{end:.4f};1"
        else:
            pre = max(0.0, start - 0.001)
            fade_at = min(0.985, max(start + 0.001, end - 0.001))
            opacity_values = "0;0;1;1;0"
            opacity_times = f"0;{pre:.4f};{start:.4f};{fade_at:.4f};1"

        groups.append(
            '<g opacity="0">'
            f'<animate attributeName="opacity" values="{opacity_values}" '
            f'keyTimes="{opacity_times}" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'<text x="1090" y="50" text-anchor="end" fill="{muted}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="8.2" letter-spacing=".5">BRICKS {remaining}</text>'
            f'<text x="1162" y="50" text-anchor="end" fill="{accent}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10.5" font-weight="700">SPD x{speed:.2f}</text>'
            '</g>'
        )

    marker = '<rect x="26" y="55"'
    index = svg.find(marker)
    if index < 0:
        raise RuntimeError("panel marker not found for status counter")
    return svg[:index] + "".join(groups) + '\n' + svg[index:]


def inject_victory(
    svg: str,
    schedule: list[dict[str, float | int]],
    duration: float,
    theme: str,
) -> str:
    if not schedule:
        return svg

    last_hit = max(float(event["frac"]) for event in schedule)
    appear = min(0.90, last_hit + VICTORY_APPEAR_PAD)
    full = min(0.93, appear + 0.022)
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
        f'<text x="600" y="160" text-anchor="middle" fill="{text}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10.5" letter-spacing=".85">100% CONTRIBUTION BRICKS DESTROYED // SINGLE BALL</text>'
        f'<circle cx="350" cy="142" r="3.5" fill="{green}"/><circle cx="850" cy="142" r="3.5" fill="{green}"/>'
        f'<text x="600" y="174" text-anchor="middle" fill="{muted}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="8.5" letter-spacing=".55">NEXT ROUND // SPEED RESET TO x1.00</text>'
        '</g>'
    )

    marker = '<text x="48" y="210" class="legend">SOURCE // GITHUB CONTRIBUTIONS</text>'
    if marker not in svg:
        raise RuntimeError("legend marker not found for victory insertion")
    return svg.replace(marker, victory + '\n' + marker, 1)


def refine(path: Path) -> None:
    svg = path.read_text(encoding="utf-8")
    theme = "dark" if "dark" in path.name else "light"
    ball_color = "#ff4d67" if theme == "dark" else "#e11d48"

    rng = random.Random(f"{SEED}:{theme}:single-ball-accelerator")
    phase = rng.random()
    bricks = collect_active_bricks(svg)
    ordered = frontline_order(bricks, rng)
    ball_path, schedule, catch_times, duration = build_single_ball_round(ordered, phase)

    svg = inject_brick_destruction(svg, schedule, duration)
    svg = replace_single_ball(svg, ball_path, schedule, duration, ball_color)
    svg = inject_hit_sparks(svg, schedule, duration, ball_color)
    svg = replace_live_paddle(svg, catch_times, phase, duration)
    svg = inject_status_counter(svg, schedule, duration, theme)
    svg = inject_victory(svg, schedule, duration, theme)

    svg = svg.replace(
        "BRICK DEFENSE // SEEDED LIVE LOOP",
        "BRICK DEFENSE // SINGLE BALL // ACCELERATING // 100% CLEAR",
        1,
    )
    desc_match = re.search(r'<desc id="desc">.*?</desc>', svg, re.S)
    if desc_match:
        svg = svg.replace(
            desc_match.group(0),
            '<desc id="desc">Brick Defense uses one red ball only. It targets each existing contribution brick exactly once from the exposed left edge to the right, rebounds instantly from the moving paddle, and accelerates after every destroyed brick until zero remain.</desc>',
            1,
        )

    path.write_text(svg, encoding="utf-8")
    final_hit = max((float(event["frac"]) for event in schedule), default=0.0)
    final_speed = speed_multiplier(len(schedule))
    print(
        f"refined {path}: active_bricks={len(bricks)} cleared={len(schedule)} "
        f"balls=1 speed_start=x1.00 speed_final=x{final_speed:.2f} "
        f"duration={fmt(duration)}s final_hit={final_hit:.4f} paddle_catches={len(catch_times)}"
    )


def main() -> int:
    for path in ASSETS:
        refine(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
