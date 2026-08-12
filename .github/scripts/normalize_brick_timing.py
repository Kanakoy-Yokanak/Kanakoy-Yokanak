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


def replace_attr(tag: str, name: str, value: str) -> str:
    pattern = re.compile(rf'{re.escape(name)}="[^"]*"')
    return pattern.sub(f'{name}="{value}"', tag, count=1)


def canonical_time(value: float) -> str:
    if abs(value) < 0.00005:
        return "0"
    if abs(value - 1.0) < 0.00005:
        return "1"
    return f"{value:.4f}"


def normalize_animate(tag: str) -> tuple[str, bool]:
    attrs = {match.group("name"): match.group("value") for match in ATTR_RE.finditer(tag)}
    raw_values = attrs.get("values")
    raw_times = attrs.get("keyTimes")
    if raw_values is None or raw_times is None:
        return tag, False

    values = raw_values.split(";")
    try:
        times = [float(part) for part in raw_times.split(";")]
    except ValueError:
        return tag, False

    if len(values) != len(times) or len(times) < 2:
        return tag, False

    # Quantize first because the SVG renderer emits four-decimal keyTimes.
    # Two distinct Python floats can therefore collapse to the same SMIL time.
    # At a duplicate instant we keep the last value, which gives the paddle a
    # single authoritative position instead of a zero-duration hold/jump.
    compact_times: list[float] = []
    compact_values: list[str] = []
    for time_value, animated_value in zip(times, values):
        quantized = round(time_value, 4)
        if compact_times and abs(quantized - compact_times[-1]) < 0.00005:
            compact_times[-1] = quantized
            compact_values[-1] = animated_value
        else:
            compact_times.append(quantized)
            compact_values.append(animated_value)

    if len(compact_times) == len(times):
        return tag, False

    # SMIL requires monotonically increasing keyTimes. Preserve the endpoints
    # and refuse to create a malformed animation if input ordering is broken.
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

    return new_tag, True


def validate(svg: str, path: Path) -> None:
    for tag in ANIMATE_RE.findall(svg):
        attrs = {match.group("name"): match.group("value") for match in ATTR_RE.finditer(tag)}
        raw_values = attrs.get("values")
        raw_times = attrs.get("keyTimes")
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

    def repl(match: re.Match[str]) -> str:
        nonlocal fixes
        tag, changed = normalize_animate(match.group(0))
        if changed:
            fixes += 1
        return tag

    normalized = ANIMATE_RE.sub(repl, svg)
    validate(normalized, path)
    path.write_text(normalized, encoding="utf-8")
    print(f"normalized {path}: timing_fixes={fixes}")


def main() -> int:
    for path in ASSETS:
        normalize(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
