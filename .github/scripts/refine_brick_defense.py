#!/usr/bin/env python3
from __future__ import annotations

import os
import random
import re
from pathlib import Path

SEED = os.environ.get("DEFENSE_SEED", "local")
ASSETS = (Path("assets/contributions-dark.svg"), Path("assets/contributions-light.svg"))
BALL_RADIUS = 6.0

BALL_X_RE = re.compile(r'<animate attributeName="cx" values="([^"]+)" keyTimes="([^"]+)" dur="([0-9.]+)s"')
BALL_Y_RE = re.compile(r'<animate attributeName="cy" values="([^"]+)" keyTimes="([^"]+)" dur="([0-9.]+)s"')
BALL_X_ANIM_RE = re.compile(
    r'(<animate attributeName="cx" values=")([^"]+)(" keyTimes="[^"]+" dur="[0-9.]+s" calcMode="linear" repeatCount="indefinite"/>)'
)
BALL_Y_ANIM_RE = re.compile(
    r'(<animate attributeName="cy" values=")([^"]+)(" keyTimes="[^"]+" dur="[0-9.]+s" calcMode="linear" repeatCount="indefinite"/>)'
)
PADDLE_GROUP_RE = re.compile(r'(<g aria-label="Horizontal defense paddle">)(.*?)(</g>)', re.S)
PADDLE_Y_RE = re.compile(r'<animate attributeName="y" values="([^"]+)" keyTimes="([^"]+)" dur="([0-9.]+)s" calcMode="linear" repeatCount="indefinite"/>')
BRICK_RE = re.compile(
    r'(<rect class="brick" x="(?P<x>-?[0-9.]+)" y="(?P<y>-?[0-9.]+)" '
    r'width="(?P<w>[0-9.]+)" height="(?P<h>[0-9.]+)"(?P<attrs>[^>]*)>)'
    r'(?P<body>.*?)</rect>',
    re.S,
)


def parse_numbers(raw: str) -> list[float]:
    return [float(part) for part in raw.split(";") if part]


def fmt(value: float) -> str:
    text = f"{value:.2f}"
    return text.rstrip("0").rstrip(".")


def smooth_paddle_track(catches: list[float], rng: random.Random) -> tuple[list[float], list[float]]:
    if len(catches) < 2:
        return catches, [0.0]

    values = [catches[0]]
    times = [0.0]
    intervals = len(catches) - 1

    for i in range(intervals):
        start = catches[i]
        end = catches[i + 1]
        t0 = i / intervals
        span = 1 / intervals
        delta = end - start

        for local_t, noise_scale in ((0.26, 2.6), (0.60, 2.2), (0.84, 1.2)):
            eased = local_t * local_t * (3 - 2 * local_t)
            human_bias = rng.uniform(-noise_scale, noise_scale)
            value = start + delta * eased + human_bias
            lo = min(start, end) - 5
            hi = max(start, end) + 5
            value = max(lo, min(hi, value))
            values.append(value)
            times.append(t0 + span * local_t)

        values.append(end)
        times.append(t0 + span)

    return values, times


def plan_frontline_hits(
    svg: str,
    ball_x: list[float],
    ball_y: list[float],
) -> tuple[list[tuple[int, float, float, float]], list[float], list[float]]:
    """Plan collisions strictly from the exposed left edge toward the right.

    Every outbound trip may destroy only a brick in the leftmost x-column that
    still contains an active contribution. Within that exposed column, choose
    the brick closest to the route's current y target. This preserves visual
    variation while making it impossible to tunnel through the frontline.
    """
    bricks: list[tuple[int, float, float, float]] = []
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
        bricks.append((match.start(), x, x + w / 2, y + h / 2))

    if not bricks:
        return [], ball_x, ball_y

    revised_x = list(ball_x)
    revised_y = list(ball_y)
    used: set[int] = set()
    hits: list[tuple[int, float, float, float]] = []
    denom = max(1, len(ball_x) - 1)

    for route_index in range(1, len(ball_x), 2):
        remaining = [brick for brick in bricks if brick[0] not in used]
        if not remaining:
            break

        front_x = min(brick[1] for brick in remaining)
        frontline = [brick for brick in remaining if abs(brick[1] - front_x) < 0.01]
        original_target_y = revised_y[route_index]
        start, left_x, center_x, center_y = min(
            frontline,
            key=lambda brick: (abs(brick[3] - original_target_y), brick[3]),
        )

        used.add(start)
        hit_fraction = route_index / denom
        hits.append((start, hit_fraction, center_x, center_y))

        # Make the ball visibly contact the exposed left face of this brick.
        revised_x[route_index] = left_x - BALL_RADIUS
        revised_y[route_index] = center_y

    return hits, revised_x, revised_y


def rewrite_ball_route(svg: str, ball_x: list[float], ball_y: list[float]) -> str:
    x_values = ";".join(fmt(value) for value in ball_x)
    y_values = ";".join(fmt(value) for value in ball_y)

    svg, x_count = BALL_X_ANIM_RE.subn(lambda m: m.group(1) + x_values + m.group(3), svg, count=2)
    svg, y_count = BALL_Y_ANIM_RE.subn(lambda m: m.group(1) + y_values + m.group(3), svg, count=2)
    if x_count != 2 or y_count != 2:
        raise RuntimeError(f"expected two ball animations, got cx={x_count} cy={y_count}")
    return svg


def inject_brick_disappear(svg: str, hits: list[tuple[int, float, float, float]], duration: float) -> str:
    hit_by_start = {start: frac for start, frac, _, _ in hits}

    def replace(match: re.Match[str]) -> str:
        frac = hit_by_start.get(match.start())
        if frac is None:
            return match.group(0)
        pre = max(0.0, frac - 0.008)
        post = min(0.995, frac + 0.018)
        anim = (
            f'<animate attributeName="opacity" values="1;1;0;0" '
            f'keyTimes="0;{pre:.4f};{post:.4f};1" dur="{fmt(duration)}s" '
            f'repeatCount="indefinite"/>'
        )
        return f'{match.group(1)}{match.group("body")}{anim}</rect>'

    return BRICK_RE.sub(replace, svg)


def inject_hit_sparks(svg: str, hits: list[tuple[int, float, float, float]], duration: float, ball_color: str) -> str:
    sparks = []
    for _, frac, x, y in hits:
        start = max(0.0, frac - 0.004)
        peak = min(0.992, frac + 0.014)
        end = min(0.997, frac + 0.055)
        sparks.append(
            f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="2.5" fill="{ball_color}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;.8;0;0" '
            f'keyTimes="0;{start:.4f};{peak:.4f};{end:.4f};1" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="r" values="2.5;2.5;11;18;18" '
            f'keyTimes="0;{start:.4f};{peak:.4f};{end:.4f};1" dur="{fmt(duration)}s" repeatCount="indefinite"/>'
            f'</circle>'
        )
    if not sparks:
        return svg
    marker = '<g aria-label="Defense ball">'
    return svg.replace(marker, '<g aria-label="Brick impact sparks">' + "".join(sparks) + '</g>\n' + marker, 1)


def refine_paddle(svg: str, rng: random.Random) -> str:
    group_match = PADDLE_GROUP_RE.search(svg)
    if not group_match:
        raise RuntimeError("paddle group not found")

    group = group_match.group(2)
    animations = list(PADDLE_Y_RE.finditer(group))
    if len(animations) < 2:
        raise RuntimeError("paddle animations not found")

    catches = parse_numbers(animations[0].group(1))
    duration = float(animations[0].group(3))
    values, times = smooth_paddle_track(catches, rng)
    splines = ";".join("0.22 0.61 0.36 1" for _ in range(max(0, len(values) - 1)))
    value_text = ";".join(fmt(v) for v in values)
    outline_text = ";".join(fmt(v - 3) for v in values)
    time_text = ";".join(f"{t:.4f}" for t in times)

    replacement_index = 0

    def repl(_: re.Match[str]) -> str:
        nonlocal replacement_index
        replacement_index += 1
        vals = value_text if replacement_index == 1 else outline_text
        return (
            f'<animate attributeName="y" values="{vals}" keyTimes="{time_text}" '
            f'keySplines="{splines}" dur="{fmt(duration)}s" calcMode="spline" '
            f'repeatCount="indefinite"/>'
        )

    new_group = PADDLE_Y_RE.sub(repl, group, count=2)
    return svg[:group_match.start(2)] + new_group + svg[group_match.end(2):]


def refine(path: Path) -> None:
    svg = path.read_text(encoding="utf-8")
    x_match = BALL_X_RE.search(svg)
    y_match = BALL_Y_RE.search(svg)
    if not x_match or not y_match:
        raise RuntimeError(f"ball route not found in {path}")

    ball_x = parse_numbers(x_match.group(1))
    ball_y = parse_numbers(y_match.group(1))
    duration = float(x_match.group(3))
    if len(ball_x) != len(ball_y):
        raise RuntimeError(f"ball route mismatch in {path}")

    rng = random.Random(f"{SEED}:paddle")
    hits, revised_x, revised_y = plan_frontline_hits(svg, ball_x, ball_y)
    svg = inject_brick_disappear(svg, hits, duration)
    svg = rewrite_ball_route(svg, revised_x, revised_y)
    ball_color = "#ff4d67" if "dark" in path.name else "#e11d48"
    svg = inject_hit_sparks(svg, hits, duration, ball_color)
    svg = refine_paddle(svg, rng)
    svg = svg.replace(
        "Contribution bricks come from GitHub and the defense route is regenerated from a workflow seed.",
        "Contribution bricks are destroyed strictly from the exposed frontline; the defense paddle follows the live loop with smoothed human-like motion.",
        1,
    )
    path.write_text(svg, encoding="utf-8")
    print(f"refined {path}: frontline_hits={len(hits)}")


def main() -> int:
    for path in ASSETS:
        refine(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
