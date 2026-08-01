#!/usr/bin/env python3
"""Render deterministic SVG figures from a VeraNav study JSON file."""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any


def _finite(value: Any, name: str) -> float:
    scalar = float(value)
    if not math.isfinite(scalar):
        raise ValueError(f"{name} must be finite")
    return scalar


def _load_study(path: Path) -> dict[str, Any]:
    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("study JSON must contain an object")
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported study schema_version")
    if not isinstance(payload.get("paired_comparison"), dict):
        raise ValueError("study JSON is missing paired_comparison")
    if not isinstance(payload.get("adaptive_boundary"), dict):
        raise ValueError("study JSON is missing adaptive_boundary")
    return payload


def _svg_document(width: int, height: int, body: str, title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-labelledby="title desc">\n'
        f'  <title id="title">{html.escape(title)}</title>\n'
        '  <desc id="desc">Deterministic figure generated from a VeraNav '
        'reliability study.</desc>\n'
        f'{body}'
        '</svg>\n'
    )


def render_reliability_boundary_svg(payload: dict[str, Any]) -> str:
    """Render the adaptive GNSS-bias reliability boundary."""
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")
    boundary = payload.get("adaptive_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("payload is missing adaptive_boundary")
    points = boundary.get("points")
    if not isinstance(points, list) or not points:
        raise ValueError("adaptive_boundary.points must be a nonempty list")

    rows = []
    for index, item in enumerate(points):
        if not isinstance(item, dict):
            raise ValueError("boundary points must be objects")
        outage = _finite(item.get("outage_duration_s"), "outage_duration_s")
        if outage < 0.0:
            raise ValueError("outage_duration_s must be nonnegative")
        status = str(item.get("status"))
        if status not in {"bounded", "all_reliable", "none_reliable"}:
            raise ValueError("invalid boundary status")
        low = item.get("lower_reliable_bias_m")
        high = item.get("upper_unreliable_bias_m")
        low_value = None if low is None else _finite(low, "lower_reliable_bias_m")
        high_value = None if high is None else _finite(high, "upper_unreliable_bias_m")
        if status == "bounded":
            if low_value is None or high_value is None or not low_value < high_value:
                raise ValueError("bounded points require an ordered bracket")
            marker = 0.5 * (low_value + high_value)
        elif status == "all_reliable":
            if low_value is None:
                raise ValueError("all_reliable points require a lower bound")
            marker = low_value
        else:
            if high_value is None:
                raise ValueError("none_reliable points require an upper bound")
            marker = high_value
        rows.append((index, outage, status, low_value, high_value, marker))

    max_outage = max(row[1] for row in rows)
    max_bias = _finite(boundary.get("max_bias_m"), "max_bias_m")
    if max_bias <= 0.0:
        raise ValueError("max_bias_m must be positive")

    width, height = 900, 520
    left, right, top, bottom = 92, 46, 78, 82
    plot_w = width - left - right
    plot_h = height - top - bottom

    def x_of(outage: float, index: int) -> float:
        if max_outage == 0.0:
            return left + plot_w * (index + 1) / (len(rows) + 1)
        return left + plot_w * outage / max_outage

    def y_of(bias: float) -> float:
        return top + plot_h * (1.0 - bias / max_bias)

    elements = [
        '  <rect width="900" height="520" fill="#ffffff"/>\n',
        '  <text x="92" y="34" font-family="Arial, sans-serif" '
        'font-size="24" font-weight="700" fill="#172033">'
        'Adaptive GNSS-bias reliability boundary</text>\n',
        '  <text x="92" y="57" font-family="Arial, sans-serif" '
        'font-size="13" fill="#5b6578">'
        'Illustrative deterministic synthetic study; not a safety claim</text>\n',
        f'  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" '
        'fill="#f7f9fc" stroke="#c9d1df"/>\n',
    ]

    for tick in range(0, 7):
        value = max_bias * tick / 6.0
        y = y_of(value)
        elements.append(
            f'  <line x1="{left}" y1="{y:.3f}" x2="{left + plot_w}" '
            f'y2="{y:.3f}" stroke="#dce2ec" stroke-width="1"/>\n'
        )
        elements.append(
            f'  <text x="{left - 12}" y="{y + 4:.3f}" text-anchor="end" '
            'font-family="Arial, sans-serif" font-size="12" fill="#5b6578">'
            f'{value:.1f}</text>\n'
        )

    for index, outage, status, low, high, marker in rows:
        x = x_of(outage, index)
        elements.append(
            f'  <line x1="{x:.3f}" y1="{top}" x2="{x:.3f}" '
            f'y2="{top + plot_h}" stroke="#e6eaf1" stroke-width="1"/>\n'
        )
        elements.append(
            f'  <text x="{x:.3f}" y="{top + plot_h + 27}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="12" fill="#334155">'
            f'{outage:g}</text>\n'
        )
        if status == "bounded":
            assert low is not None and high is not None
            y_low = y_of(low)
            y_high = y_of(high)
            elements.append(
                f'  <line x1="{x:.3f}" y1="{y_low:.3f}" x2="{x:.3f}" '
                f'y2="{y_high:.3f}" stroke="#d97706" stroke-width="10" '
                'stroke-linecap="round"/>\n'
            )
            elements.append(
                f'  <circle cx="{x:.3f}" cy="{y_of(marker):.3f}" r="7" '
                'fill="#1d4ed8" stroke="#ffffff" stroke-width="2"/>\n'
            )
            label = f"{low:.3f}-{high:.3f} m"
        elif status == "all_reliable":
            elements.append(
                f'  <circle cx="{x:.3f}" cy="{y_of(marker):.3f}" r="7" '
                'fill="#15803d" stroke="#ffffff" stroke-width="2"/>\n'
            )
            elements.append(
                f'  <path d="M {x:.3f} {y_of(marker) - 7:.3f} '
                f'L {x - 5:.3f} {y_of(marker) - 17:.3f} '
                f'L {x + 5:.3f} {y_of(marker) - 17:.3f} Z" fill="#15803d"/>\n'
            )
            label = f"reliable through {marker:.3f} m"
        else:
            elements.append(
                f'  <circle cx="{x:.3f}" cy="{y_of(marker):.3f}" r="7" '
                'fill="#b91c1c" stroke="#ffffff" stroke-width="2"/>\n'
            )
            label = f"unreliable from {marker:.3f} m"

        label_y = min(top + plot_h - 8, max(top + 18, y_of(marker) + 27))
        elements.append(
            f'  <text x="{x:.3f}" y="{label_y:.3f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="11" fill="#334155">'
            f'{html.escape(label)}</text>\n'
        )

    elements.extend(
        [
            f'  <text x="{left + plot_w / 2:.3f}" y="{height - 24}" '
            'text-anchor="middle" font-family="Arial, sans-serif" '
            'font-size="14" font-weight="600" fill="#172033">'
            'GNSS outage duration (s)</text>\n',
            f'  <text x="24" y="{top + plot_h / 2:.3f}" '
            'text-anchor="middle" font-family="Arial, sans-serif" '
            'font-size="14" font-weight="600" fill="#172033" '
            f'transform="rotate(-90 24 {top + plot_h / 2:.3f})">'
            'GNSS bias magnitude (m)</text>\n',
            '  <circle cx="627" cy="42" r="6" fill="#1d4ed8"/>\n',
            '  <text x="641" y="46" font-family="Arial, sans-serif" '
            'font-size="11" fill="#334155">bounded transition</text>\n',
            '  <circle cx="760" cy="42" r="6" fill="#15803d"/>\n',
            '  <text x="774" y="46" font-family="Arial, sans-serif" '
            'font-size="11" fill="#334155">all reliable in range</text>\n',
        ]
    )
    return _svg_document(width, height, "".join(elements), "VeraNav reliability boundary")


def render_paired_rmse_svg(payload: dict[str, Any]) -> str:
    """Render seed-wise paired RMSE differences."""
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")
    comparison = payload.get("paired_comparison")
    if not isinstance(comparison, dict):
        raise ValueError("payload is missing paired_comparison")
    runs = comparison.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("paired_comparison.runs must be a nonempty list")

    values = []
    for item in runs:
        if not isinstance(item, dict):
            raise ValueError("paired runs must be objects")
        seed = int(item.get("seed"))
        delta = _finite(item.get("rmse_difference_m"), "rmse_difference_m")
        values.append((seed, delta))

    interval = comparison.get("rmse_difference_interval_m")
    if not isinstance(interval, dict):
        raise ValueError("missing rmse_difference_interval_m")
    estimate = _finite(interval.get("estimate"), "estimate")
    lower = _finite(interval.get("lower"), "lower")
    upper = _finite(interval.get("upper"), "upper")

    width, height = 900, 500
    left, right, top, bottom = 92, 46, 80, 82
    plot_w = width - left - right
    plot_h = height - top - bottom
    min_value = min(0.0, lower, *(value for _, value in values))
    max_value = max(0.0, upper, *(value for _, value in values))
    padding = max(0.02, 0.12 * max(max_value - min_value, 0.01))
    y_min = min_value - padding
    y_max = max_value + padding

    def y_of(value: float) -> float:
        return top + plot_h * (1.0 - (value - y_min) / (y_max - y_min))

    step = plot_w / len(values)
    bar_width = min(52.0, step * 0.58)
    zero_y = y_of(0.0)

    elements = [
        '  <rect width="900" height="500" fill="#ffffff"/>\n',
        '  <text x="92" y="34" font-family="Arial, sans-serif" '
        'font-size="24" font-weight="700" fill="#172033">'
        'Paired RMSE effect by random seed</text>\n',
        '  <text x="92" y="57" font-family="Arial, sans-serif" '
        'font-size="13" fill="#5b6578">'
        'Degraded minus baseline; positive values indicate worse RMSE</text>\n',
        f'  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" '
        'fill="#f7f9fc" stroke="#c9d1df"/>\n',
    ]

    for tick in range(0, 6):
        value = y_min + (y_max - y_min) * tick / 5.0
        y = y_of(value)
        elements.append(
            f'  <line x1="{left}" y1="{y:.3f}" x2="{left + plot_w}" '
            f'y2="{y:.3f}" stroke="#dce2ec" stroke-width="1"/>\n'
        )
        elements.append(
            f'  <text x="{left - 12}" y="{y + 4:.3f}" text-anchor="end" '
            'font-family="Arial, sans-serif" font-size="12" fill="#5b6578">'
            f'{value:.3f}</text>\n'
        )

    elements.append(
        f'  <line x1="{left}" y1="{zero_y:.3f}" x2="{left + plot_w}" '
        f'y2="{zero_y:.3f}" stroke="#334155" stroke-width="1.5"/>\n'
    )

    for index, (seed, value) in enumerate(values):
        x_center = left + step * (index + 0.5)
        value_y = y_of(value)
        y = min(zero_y, value_y)
        height_value = abs(zero_y - value_y)
        fill = "#2563eb" if value >= 0.0 else "#64748b"
        elements.append(
            f'  <rect x="{x_center - bar_width / 2:.3f}" y="{y:.3f}" '
            f'width="{bar_width:.3f}" height="{max(height_value, 1.0):.3f}" '
            f'fill="{fill}" rx="3"/>\n'
        )
        elements.append(
            f'  <text x="{x_center:.3f}" y="{top + plot_h + 25}" '
            'text-anchor="middle" font-family="Arial, sans-serif" '
            'font-size="12" fill="#334155">'
            f'{seed}</text>\n'
        )

    estimate_y = y_of(estimate)
    lower_y = y_of(lower)
    upper_y = y_of(upper)
    elements.extend(
        [
            f'  <line x1="{left}" y1="{estimate_y:.3f}" '
            f'x2="{left + plot_w}" y2="{estimate_y:.3f}" '
            'stroke="#b45309" stroke-width="2" stroke-dasharray="7 5"/>\n',
            f'  <rect x="{left + plot_w - 190}" y="{min(lower_y, upper_y):.3f}" '
            f'width="180" height="{abs(lower_y - upper_y):.3f}" '
            'fill="#f59e0b" fill-opacity="0.16"/>\n',
            f'  <text x="{left + plot_w - 8}" y="{estimate_y - 7:.3f}" '
            'text-anchor="end" font-family="Arial, sans-serif" '
            'font-size="11" fill="#92400e">'
            f'mean {estimate:.3f} m, 95% CI [{lower:.3f}, {upper:.3f}]</text>\n',
            f'  <text x="{left + plot_w / 2:.3f}" y="{height - 24}" '
            'text-anchor="middle" font-family="Arial, sans-serif" '
            'font-size="14" font-weight="600" fill="#172033">'
            'Paired random seed</text>\n',
            f'  <text x="24" y="{top + plot_h / 2:.3f}" '
            'text-anchor="middle" font-family="Arial, sans-serif" '
            'font-size="14" font-weight="600" fill="#172033" '
            f'transform="rotate(-90 24 {top + plot_h / 2:.3f})">'
            'RMSE difference (m)</text>\n',
        ]
    )
    return _svg_document(width, height, "".join(elements), "VeraNav paired RMSE effects")


def write_study_svgs(study_json: Path, output_dir: Path) -> tuple[Path, Path]:
    """Write deterministic reliability-boundary and paired-effect SVG files."""
    if not isinstance(study_json, Path):
        raise TypeError("study_json must be a pathlib.Path")
    if not isinstance(output_dir, Path):
        raise TypeError("output_dir must be a pathlib.Path")
    payload = _load_study(study_json)
    output_dir.mkdir(parents=True, exist_ok=True)
    boundary_path = output_dir / "reliability_boundary.svg"
    paired_path = output_dir / "paired_rmse_differences.svg"
    boundary_path.write_text(
        render_reliability_boundary_svg(payload),
        encoding="utf-8",
        newline="\n",
    )
    paired_path.write_text(
        render_paired_rmse_svg(payload),
        encoding="utf-8",
        newline="\n",
    )
    return boundary_path, paired_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render deterministic SVG figures from a VeraNav study JSON.",
    )
    parser.add_argument("study_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    for path in write_study_svgs(args.study_json, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()


__all__ = [
    "render_paired_rmse_svg",
    "render_reliability_boundary_svg",
    "write_study_svgs",
]
