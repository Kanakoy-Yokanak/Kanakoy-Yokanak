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
HIT_START = 0.075
HIT_END = 0.795
VICTORY_APPEAR_PAD = 0.030
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


def frontline_order(
    bricks: list[dict[str, float | int]],
    rng: random.Random,
) -> list[dict[str, float | int]]:
    """Clear every active contribution from the exposed left edge to the right."""
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
    # One ball becomes two, then three, then four. The round accelerates as the
    # field fills with balls but stays readable in the profile README.
    return clamp(24.0 + active_count * 0.72, 44.0, 86.0)


def build_hit_schedule(
    ordered: list[dict[str, float | int]],
) -> list[dict[str, float | int]]:
    if not ordered:
        return []

    weights: list[float] = []
    previous_x: float | None = None
    for index, brick in enumerate(ordered):
        x = float(brick["left_x"])
        # Early hits are a little farther apart so 1 -> 2 -> 3 is readable.
        # Later hits accelerate because there are many balls on the field.
        growth = 1.28 - min(0.52, index * 0.016)
        column_pause = 0.34 if previous_x is not None and abs(x - previous_x) > 0.01 else 0.0
        weights.append(growth + column_pause)
        previous_x = x

    total_weight = sum(weights)
    cumulative = 0.0
    schedule: list[dict[str, float | int]] = []
    for index, (brick, weight) in enumerate(zip(ordered, weights)):
        midpoint = cumulative + weight * 0.5
        frac = HIT_START + (HIT_END - HIT_START) * (midpoint / total_weight)
        event = dict(brick)
        event["frac"] = frac
        event["index"] = index
        schedule.append(event)
        cumulative += weight
    return schedule


def paddle_center(t: float, phase: float) -> float:
    """Continuous moving defense shared by the paddle and every ball catch."""
    center_min = FIELD_TOP + PADDLE_H / 2 + 2
    center_max = FIELD_BOTTOM - PADDLE_H / 2 - 2
    raw = (
        144.0
        + 29.0 * math.sin(2 * math.pi * (2.15 * t + phase))
        + 10.5 * math.sin(2 * math.pi * (5.35 * t + phase * 0.37))
        + 4.5 * math.sin(2 * math.pi * (9.10 * t + phase * 0.13))
    )
    return clamp(raw, center_min, center_max)


def build_attacker_paths(
    schedule: list[dict[str, float | int]],
    phase: float,
) -> list[list[tuple[float, float, float]]]:
    """Build the multiplier chain: x1, then one new live ball per destroyed brick.

    Ball 1 starts the round. A destroyed brick spawns one new ball exactly at
    the impact. That new ball returns to the moving paddle and immediately
    rebounds toward the next exposed frontline brick. There is no paddle dwell.
    """
    ball_count = len(schedule) + 1
    paths: list[list[tuple[float, float, float]]] = [[] for _ in range(ball_count)]

    initial_y = paddle_center(0.0, phase)
    paths[0].append((0.0, BALL_HOME_X, initial_y))

    if not schedule:
        paths[0].append((1.0, 410.0, initial_y))
        return paths

    first = schedule[0]
    first_t = float(first["frac"])
    paths[0].append((first_t, float(first["left_x"]) - BALL_RADIUS, float(first["center_y"])))

    for index in range(1, ball_count):
        born = schedule[index - 1]
        birth_t = float(born["frac"])
        birth_x = float(born["left_x"]) - BALL_RADIUS
        birth_y = float(born["center_y"])
        paths[index].append((birth_t, birth_x, birth_y))

        if index < len(schedule):
            target = schedule[index]
            hit_t = float(target["frac"])
            catch_t = birth_t + (hit_t - birth_t) * 0.48
            catch_y = paddle_center(catch_t, phase)
            paths[index].append((catch_t, BALL_HOME_X, catch_y))
            # The very next segment leaves the paddle toward the next brick.
            # One contact keyframe means an instantaneous rebound, not a hold.
            paths[index].append((hit_t, float(target["left_x"]) - BALL_RADIUS, float(target["center_y"])))

    return paths


def add_roaming_bounces(
    paths: list[list[tuple[float, float, float]]],
    schedule: list[dict[str, float | int]],
    rng: random.Random,
    phase: float,
) -> tuple[list[list[tuple[float, float, float]]], list[float]]:
    """Keep old multiplied balls alive, moving, and repeatedly defended."""
    paddle_times: list[float] = [0.0]

    for ball_id, path in enumerate(paths):
        if not path:
            continue

        start_t, _, start_y = path[-1]
        if start_t >= 0.90:
            continue

        remaining = max(0.0, 0.91 - start_t)
        loops = max(1, min(5, int(remaining / 0.105) + 1))
        cursor = start_t
        current_y = start_y

        for loop in range(loops):
            room = 0.91 - cursor
            if room < 0.018:
                break

            segment = min(0.070 + (ball_id % 4) * 0.004, room * 0.82)
            catch_t = cursor + segment * 0.46
            away_t = cursor + segment
            catch_y = paddle_center(catch_t, phase)
            away_x = 255.0 + ((ball_id * 53 + loop * 97) % 350)
            away_y = clamp(
                catch_y + rng.uniform(-44.0, 44.0),
                FIELD_TOP + BALL_RADIUS + 2,
                FIELD_BOTTOM - BALL_RADIUS - 2,
            )

            # away -> paddle -> away: the ball never parks on the paddle.
            path.append((catch_t, BALL_HOME_X, catch_y))
            path.append((away_t, away_x, away_y))
            paddle_times.append(catch_t)
            cursor = away_t
            current_y = away_y

        if path[-1][0] < 0.93:
            end_t = min(0.93, path[-1][0] + 0.035)
            end_x = 340.0 + ((ball_id * 41) % 300)
            end_y = clamp(
                current_y + rng.uniform(-26.0, 26.0),
                FIELD_TOP + BALL_RADIUS + 2,
                FIELD_BOTTOM - BALL_RADIUS - 2,
            )
            path.append((end_t, end_x, end_y))

    # Exact attacker-chain paddle contacts are added to the paddle timeline.
    for index in range(1, len(schedule)):
        birth_t = float(schedule[index - 1]["frac"])
        hit_t = float(schedule[index]["frac"])
        paddle_times.append(birth_t + (hit_t - birth_t) * 0.48)

    return paths, paddle_times


def compact_path(points: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    points = sorted(points, key=lambda point: point[0])
    compact: list[tuple[float, float, float]] = []
    for point in points:
        if compact and abs(point[0] - compact[-1][0]) < 0.00035:
            compact[-1] = point
        else:
            compact.append(point)

    if compact and compact[-1][0] < 1.0:
        last_t, last_x, last_y = compact[-1]
        compact.append((1.0, last_x, last_y))
    return compact


def replace_growing_multiball(
    svg: str,
    paths: list[list[tuple[float, float, float]]],
    schedule: list[dict[str, float | int]],
    duration: float,
    ball_color: str,
) -> str:
    groups: list[str] = []
    fade_start = min(
        0.94,
        (float(schedule[-1]["frac"]) + VICTORY_APPEAR_PAD) if schedule else 0.88,
    )

    for ball_id, raw_path in enumerate(paths):
        path = compact_path(raw_path)
        if not path:
            continue

        birth_t = path[0][0]
        x_values = ";".join(fmt(point[1]) for point in path)
        y_values = ";".join(fmt(point[2]) for point in path)
        key_times = ";".join(f"{point[0]:.4f}" for point in path)
        x0, y0 = path[0][1], path[0][2]

        if ball_id == 0:
            opacity_values = "1;1;0;0"
            opacity_times = f"0;{fade_start:.4f};{min(0.975, fade_start + 0.025):.4f};1"
        else:
            appear = min(0.96, birth_t + 0.003)
            opacity_values = "0;0;1;1;0;0"
            opacity_times = (
                f"0;{birth_t:.4f};{appear:.4f};{fade_start:.4f};"
                f"{min(0.975, fade_start + 0.025):.4f};1"
            )

        groups.append(
            f'<g aria-label="Defense ball {ball_id + 1} of growing multiplier">'
            f'<animate attributeName="opacity" values="{opacity_values}" keyTimes="{opacity_times}" '
            f'dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'<circle cx="{fmt(x0)}" cy="{fmt(y0)}" r="11" fill="{ball_color}" opacity=".075" filter="url(#ballGlow)">'
            f'<animate attributeName="cx" values="{x_values}" keyTimes="{key_times}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{y_values}" keyTimes="{key_times}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
            f'</circle>'
            f'<circle cx="{fmt(x0)}" cy="{fmt(y0)}" r="{fmt(BALL_RADIUS)}" fill="{ball_color}" filter="url(#ballGlow)">'
            f'<animate attributeName="cx" values="{x_values}" keyTimes="{key_times}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{y_values}" keyTimes="{key_times}" dur="{fmt(duration)}s" calcMode="linear" repeatCount="indefinite"/>'
            f'</circle>'
            f'</g>'
        )

    replacement = (
        f'<g aria-label="Defense growing multiball 1 to {len(paths)}">'
        + "".join(groups)
        + '</g>'
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
        pre = max(0.0, frac - 0.005)
        flash = min(0.994, frac + 0.006)
        gone = min(0.997, frac + 0.018)
        anim = (
            f'<animate attributeName="opacity" values="1;1;.15;0;0" '
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
        start = max(0.0, frac - 0.003)
        peak = min(0.992, frac + 0.007)
        end = min(0.997, frac + 0.027)
        sparks.append(
            f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="2.1" fill="{ball_color}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;.9;0;0" '
            f'keyTimes="0;{start:.4f};{peak:.4f};{end:.4f};1" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="r" values="2.1;2.1;7.5;14;14" '
            f'keyTimes="0;{start:.4f};{peak:.4f};{end:.4f};1" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'</circle>'
        )

    if not sparks:
        return svg
    marker = '<g aria-label="Defense growing multiball'
    insertion = '<g aria-label="Brick impact sparks">' + "".join(sparks) + '</g>\n'
    index = svg.find(marker)
    if index < 0:
        raise RuntimeError("growing multiball marker not found")
    return svg[:index] + insertion + svg[index:]


def replace_live_paddle(
    svg: str,
    paddle_times: list[float],
    phase: float,
    duration: float,
) -> str:
    # Regular samples keep the bar visibly alive. Exact catch timestamps force
    # the bar to be centered on every ball at the instant of contact.
    times = {i / 44 for i in range(45)}
    times.update(t for t in paddle_times if 0.0 <= t <= 0.94)
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


def inject_multiplier_counter(
    svg: str,
    schedule: list[dict[str, float | int]],
    duration: float,
    theme: str,
) -> str:
    if not schedule:
        return svg

    text_color = "#ff6b80" if theme == "dark" else "#be123c"
    muted = "#7f95a9" if theme == "dark" else "#64748b"
    groups: list[str] = []
    total_balls = len(schedule) + 1
    boundaries = [0.0] + [float(event["frac"]) + 0.003 for event in schedule] + [1.0]

    for ball_count in range(1, total_balls + 1):
        start = boundaries[ball_count - 1]
        end = boundaries[ball_count]
        pre = max(0.0, start - 0.001)
        fade_at = min(0.985, max(start + 0.001, end - 0.001))
        groups.append(
            f'<g opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;1;0" '
            f'keyTimes="0;{pre:.4f};{start:.4f};{fade_at:.4f};1" '
            f'dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'<text x="1112" y="50" text-anchor="end" fill="{muted}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="8.4" letter-spacing=".55">BALLS</text>'
            f'<text x="1162" y="50" text-anchor="end" fill="{text_color}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11.5" font-weight="700">x{ball_count}</text>'
            f'</g>'
        )

    marker = '<rect x="26" y="55"'
    index = svg.find(marker)
    if index < 0:
        raise RuntimeError("panel marker not found for multiplier counter")
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
    final_balls = len(schedule) + 1

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
        f'<text x="600" y="160" text-anchor="middle" fill="{text}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10.5" letter-spacing=".85">100% CONTRIBUTION BRICKS DESTROYED // BALLS x{final_balls}</text>'
        f'<circle cx="350" cy="142" r="3.5" fill="{green}"/><circle cx="850" cy="142" r="3.5" fill="{green}"/>'
        f'<text x="600" y="174" text-anchor="middle" fill="{muted}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="8.5" letter-spacing=".55">NEXT ROUND // RESET TO x1</text>'
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

    rng = random.Random(f"{SEED}:{theme}:growing-multiball")
    phase = rng.random()
    bricks = collect_active_bricks(svg)
    ordered = frontline_order(bricks, rng)
    schedule = build_hit_schedule(ordered)
    duration = cycle_duration(len(ordered))

    paths = build_attacker_paths(schedule, phase)
    paths, paddle_times = add_roaming_bounces(paths, schedule, rng, phase)

    svg = inject_brick_destruction(svg, schedule, duration)
    svg = replace_growing_multiball(svg, paths, schedule, duration, ball_color)
    svg = inject_hit_sparks(svg, schedule, duration, ball_color)
    svg = replace_live_paddle(svg, paddle_times, phase, duration)
    svg = inject_multiplier_counter(svg, schedule, duration, theme)
    svg = inject_victory(svg, schedule, duration, theme)

    final_balls = len(schedule) + 1
    svg = svg.replace(
        "BRICK DEFENSE // SEEDED LIVE LOOP",
        "BRICK DEFENSE // x1 GROWING MULTIPLIER // 100% CLEAR",
        1,
    )
    desc_match = re.search(r'<desc id="desc">.*?</desc>', svg, re.S)
    if desc_match:
        svg = svg.replace(
            desc_match.group(0),
            '<desc id="desc">Brick Defense starts with one red ball. Every destroyed frontline contribution brick spawns one additional live ball. All balls rebound instantly from the moving defense paddle until the field reaches 100 percent clear.</desc>',
            1,
        )

    path.write_text(svg, encoding="utf-8")
    final_hit = max((float(event["frac"]) for event in schedule), default=0.0)
    print(
        f"refined {path}: active_bricks={len(bricks)} cleared={len(schedule)} "
        f"balls_start=1 balls_final={final_balls} duration={fmt(duration)}s "
        f"final_hit={final_hit:.4f} paddle_catches={len(paddle_times)}"
    )


def main() -> int:
    for path in ASSETS:
        refine(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
