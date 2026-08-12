#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ASSETS = (
    Path("assets/contributions-dark.svg"),
    Path("assets/contributions-light.svg"),
)

ANIMATE_RE = re.compile(r"<animate\b[^>]*/>")
ATTR_RE = re.compile(r'(?P<name>[A-Za-z:]+)="(?P<value>[^"]*)"')
MOTION_ATTRIBUTES = {"cx", "cy"}
EPSILON = 0.00005


def replace_attr(tag: str, name: str, value: str) -> str:
    pattern = re.compile(rf'{re.escape(name)}="[^"]*"')
    return pattern.sub(f'{name}="{value}"', tag, count=1)


def canonical_time(value: float) -> str:
    if abs(value) < EPSILON:
        return "0"
    if abs(value - 1.0) < EPSILON:
        return "1"
    return f"{value:.4f}"


def normalize_animate(tag: str) -> tuple[str, bool, bool]:
    attrs = {match.group("name"): match.group("value") for match in ATTR_RE.finditer(tag)}
    raw_values = attrs.get("values")
    raw_times = attrs.get("keyTimes")
    attribute_name = attrs.get("attributeName", "")
    if raw_values is None or raw_times is None:
        return tag, False, False

    values = raw_values.split(";")
    try:
        times = [float(part) for part in raw_times.split(";")]
    except ValueError:
        return tag, False, False

    if len(values) != len(times) or len(times) < 2:
        return tag, False, False

    # Quantize first because the renderer emits four-decimal keyTimes. Two
    # distinct Python floats can collapse to the same SMIL instant. At a
    # duplicate instant keep the last value so there is one authoritative
    # position rather than a zero-duration hold/jump.
    compact_times: list[float] = []
    compact_values: list[str] = []
    duplicate_fix = False
    for time_value, animated_value in zip(times, values):
        quantized = round(time_value, 4)
        if compact_times and abs(quantized - compact_times[-1]) < EPSILON:
            compact_times[-1] = quantized
            compact_values[-1] = animated_value
            duplicate_fix = True
        else:
            compact_times.append(quantized)
            compact_values.append(animated_value)

    # Child balls are invisible before their birth time, but their cx/cy SMIL
    # animations still must begin at keyTime=0. Without this prefix GitHub can
    # ignore the motion animation while still honoring opacity, which leaves a
    # newly visible ball frozen at the destroyed brick. Duplicate the birth
    # position at t=0: it remains invisible there, then immediately travels to
    # the paddle once its opacity turns on at birth.
    motion_boundary_fix = False
    if attribute_name in MOTION_ATTRIBUTES:
        if compact_times[0] < -EPSILON or compact_times[-1] > 1.0 + EPSILON:
            raise RuntimeError(
                f"motion keyTimes outside SMIL range for {attribute_name}: {raw_times}"
            )
        if compact_times[0] > EPSILON:
            compact_times.insert(0, 0.0)
            compact_values.insert(0, compact_values[0])
            motion_boundary_fix = True
        else:
            compact_times[0] = 0.0

        if compact_times[-1] < 1.0 - EPSILON:
            compact_times.append(1.0)
            compact_values.append(compact_values[-1])
            motion_boundary_fix = True
        else:
            compact_times[-1] = 1.0

    changed = duplicate_fix or motion_boundary_fix
    if not changed:
        return tag, False, False

    # SMIL requires monotonically increasing keyTimes. Preserve endpoints and
    # refuse to create malformed output if input ordering is broken.
    for left, right in zip(compact_times, compact_times[1:]):
        if right <= left:
            raise RuntimeError(f"non-increasing keyTimes after normalization: {raw_times}")

    new_tag = replace_attr(tag, "values", ";".join(compact_values))
    new_tag = replace_attr(
        new_tag,
        "keyTimes",
        ";".join(canonical_time(value) for value in compact_times),
    )

    raw_splines = attrs.get("keySplines")
    if raw_splines is not None:
        splines = raw_splines.split(";") if raw_splines else []
        spline = splines[0] if splines else "0.25 0.10 0.25 1"
        new_tag = replace_attr(
            new_tag,
            "keySplines",
            ";".join(spline for _ in range(len(compact_times) - 1)),
        )

    return new_tag, True, motion_boundary_fix


def validate(svg: str, path: Path) -> None:
    for tag in ANIMATE_RE.findall(svg):
        attrs = {match.group("name"): match.group("value") for match in ATTR_RE.finditer(tag)}
        raw_values = attrs.get("values")
        raw_times = attrs.get("keyTimes")
        attribute_name = attrs.get("attributeName", "")
        if raw_values is None or raw_times is None:
            continue

        values = raw_values.split(";")
        times = [float(part) for part in raw_times.split(";")]
        if len(values) != len(times):
            raise RuntimeError(
                f"values/keyTimes mismatch in {path}: {len(values)} != {len(times)}"
            )

        for left, right in zip(times, times[1:]):
            if right <= left:
                raise RuntimeError(
                    f"duplicate/non-increasing keyTimes remain in {path}: {raw_times}"
                )

        if attribute_name in MOTION_ATTRIBUTES:
            if abs(times[0]) > EPSILON:
                raise RuntimeError(
                    f"motion keyTimes must begin at 0 in {path}: {raw_times}"
                )
            if abs(times[-1] - 1.0) > EPSILON:
                raise RuntimeError(
                    f"motion keyTimes must end at 1 in {path}: {raw_times}"
                )

        raw_splines = attrs.get("keySplines")
        if raw_splines is not None:
            splines = raw_splines.split(";") if raw_splines else []
            if len(splines) != len(times) - 1:
                raise RuntimeError(
                    f"keySplines/keyTimes mismatch in {path}: "
                    f"{len(splines)} != {len(times) - 1}"
                )


def normalize(path: Path) -> None:
    svg = path.read_text(encoding="utf-8")
    fixes = 0
    motion_boundary_fixes = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal fixes, motion_boundary_fixes
        tag, changed, motion_changed = normalize_animate(match.group(0))
        if changed:
            fixes += 1
        if motion_changed:
            motion_boundary_fixes += 1
        return tag

    normalized = ANIMATE_RE.sub(repl, svg)
    validate(normalized, path)
    path.write_text(normalized, encoding="utf-8")
    print(
        f"normalized {path}: timing_fixes={fixes} "
        f"motion_boundary_fixes={motion_boundary_fixes}"
    )


def main() -> int:
    for path in ASSETS:
        normalize(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
