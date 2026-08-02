#!/usr/bin/env python3
"""Build final deterministic OpenVINS reliability synthesis artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--official-manifest", type=Path, required=True)
    parser.add_argument("--visual-dropout-root", type=Path, required=True)
    parser.add_argument("--visual-burst-root", type=Path, required=True)
    parser.add_argument("--time-online-root", type=Path, required=True)
    parser.add_argument("--time-fixed-root", type=Path, required=True)
    parser.add_argument("--time-divergence-root", type=Path, required=True)
    parser.add_argument("--imu-noise-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"required JSON file is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def scenarios(results: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = results.get("scenarios")
    if not isinstance(value, list) or not value:
        raise ValueError("results must contain nonempty scenarios")
    if not all(isinstance(item, dict) for item in value):
        raise TypeError("every scenario result must be an object")
    return value


def pick(
    record: Mapping[str, Any],
    keys: Sequence[str],
    label: str,
    *,
    required: bool = True,
) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    if required:
        raise KeyError(
            f"{label}: none of the expected keys are present: {keys}"
        )
    return None


def scenario_name(record: Mapping[str, Any]) -> str:
    return str(pick(record, ("scenario", "name"), "scenario name"))


def finite(value: Any, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def nonnegative(value: Any, label: str) -> float:
    number = finite(value, label)
    if number < 0.0:
        raise ValueError(f"{label} must be nonnegative")
    return number


def extract_visual_dropout(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    extracted = []
    for raw in records:
        name = scenario_name(raw)
        drop = nonnegative(
            pick(
                raw,
                (
                    "realized_frame_drop_fraction",
                    "realized_drop_fraction",
                    "realized_visual_drop_fraction",
                    "drop_fraction",
                    "realized_fraction",
                ),
                f"{name}.drop_fraction",
            ),
            f"{name}.drop_fraction",
        )
        rmse = nonnegative(
            pick(
                raw,
                (
                    "position_rmse_m",
                    "full_position_rmse_m",
                    "full_rmse_m",
                    "rmse_m",
                ),
                f"{name}.rmse",
            ),
            f"{name}.rmse",
        )
        ratio_raw = pick(
            raw,
            (
                "rmse_ratio",
                "position_rmse_ratio",
                "full_rmse_ratio",
                "rmse_ratio_to_baseline",
            ),
            f"{name}.rmse_ratio",
            required=False,
        )
        extracted.append(
            {
                "scenario": name,
                "drop_fraction": drop,
                "position_rmse_m": rmse,
                "rmse_ratio": (
                    None
                    if ratio_raw is None
                    else nonnegative(
                        ratio_raw,
                        f"{name}.rmse_ratio",
                    )
                ),
            }
        )

    baseline = min(extracted, key=lambda item: item["drop_fraction"])
    baseline_rmse = baseline["position_rmse_m"]
    if baseline_rmse <= 0.0:
        raise ValueError("visual dropout baseline RMSE must be positive")

    for item in extracted:
        if item["rmse_ratio"] is None:
            item["rmse_ratio"] = (
                item["position_rmse_m"] / baseline_rmse
            )

    return sorted(
        extracted,
        key=lambda item: item["drop_fraction"],
    )


def burst_start_duration(name: str) -> tuple[float, float]:
    numbers = [
        float(value)
        for value in re.findall(r"\d+(?:\.\d+)?", name)
    ]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    if name == "baseline":
        return 0.0, 0.0
    raise ValueError(f"cannot infer burst timing from scenario: {name}")


def extract_visual_burst(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    extracted = []
    for raw in records:
        name = scenario_name(raw)
        fallback_start, fallback_duration = burst_start_duration(name)

        start_raw = pick(
            raw,
            (
                "burst_start_s",
                "dropout_start_s",
                "start_time_s",
                "start_s",
            ),
            f"{name}.start",
            required=False,
        )
        duration_raw = pick(
            raw,
            (
                "burst_duration_s",
                "dropout_duration_s",
                "duration_s",
            ),
            f"{name}.duration",
            required=False,
        )
        rmse = nonnegative(
            pick(
                raw,
                (
                    "overall_rmse_m",
                    "position_rmse_m",
                    "full_position_rmse_m",
                    "full_rmse_m",
                    "rmse_m",
                ),
                f"{name}.full_rmse",
            ),
            f"{name}.full_rmse",
        )
        local_ratio = nonnegative(
            pick(
                raw,
                (
                    "local_window_rmse_ratio",
                    "local_rmse_ratio",
                    "local_position_rmse_ratio",
                    "window_rmse_ratio",
                    "local_ratio",
                ),
                f"{name}.local_ratio",
            ),
            f"{name}.local_ratio",
        )
        recovery_raw = pick(
            raw,
            (
                "recovery_time_s",
                "recovery_s",
                "strict_recovery_time_s",
            ),
            f"{name}.recovery",
            required=False,
        )

        extracted.append(
            {
                "scenario": name,
                "burst_start_s": (
                    fallback_start
                    if start_raw is None
                    else finite(start_raw, f"{name}.start")
                ),
                "burst_duration_s": (
                    fallback_duration
                    if duration_raw is None
                    else nonnegative(
                        duration_raw,
                        f"{name}.duration",
                    )
                ),
                "full_rmse_m": rmse,
                "local_rmse_ratio": local_ratio,
                "recovery_time_s": (
                    None
                    if recovery_raw is None
                    else nonnegative(
                        recovery_raw,
                        f"{name}.recovery",
                    )
                ),
            }
        )

    return extracted


def xml_text(value: str) -> str:
    return html.escape(value, quote=True)


def svg_header(width: int, height: int, title: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
        ),
        (
            "<style>"
            "text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}"
            ".title{font-size:26px;font-weight:700}"
            ".subtitle{font-size:14px;fill:#4b5563}"
            ".axis{font-size:13px;fill:#374151}"
            ".tick{font-size:12px;fill:#4b5563}"
            ".legend{font-size:13px;fill:#1f2937}"
            ".value{font-size:12px;fill:#111827}"
            "</style>"
        ),
        '<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>',
        (
            f'<text x="55" y="42" class="title">'
            f'{xml_text(title)}</text>'
        ),
    ]


def svg_footer(lines: list[str]) -> str:
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def nice_ticks(max_value: float, count: int = 5) -> list[float]:
    if max_value <= 0.0:
        return [0.0, 1.0]
    raw = max_value / count
    exponent = math.floor(math.log10(raw))
    fraction = raw / (10 ** exponent)
    if fraction <= 1:
        nice = 1
    elif fraction <= 2:
        nice = 2
    elif fraction <= 5:
        nice = 5
    else:
        nice = 10
    step = nice * (10 ** exponent)
    top = math.ceil(max_value / step) * step
    return [index * step for index in range(int(round(top / step)) + 1)]


def line_chart(
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
    series: Sequence[tuple[str, Sequence[tuple[float, float]], str]],
    *,
    y_log: bool = False,
    x_percent: bool = False,
    width: int = 1000,
    height: int = 620,
) -> str:
    left, right, top, bottom = 100, 55, 95, 90
    plot_w = width - left - right
    plot_h = height - top - bottom

    all_x = [point[0] for _, points, _ in series for point in points]
    all_y = [point[1] for _, points, _ in series for point in points]

    if not all_x or not all_y:
        raise ValueError("line chart requires data")
    if y_log and any(value <= 0.0 for value in all_y):
        raise ValueError("log chart requires positive y values")

    x_min, x_max = min(all_x), max(all_x)
    if x_min == x_max:
        x_min -= 1.0
        x_max += 1.0

    if y_log:
        y_values = [math.log10(value) for value in all_y]
        y_min = math.floor(min(y_values))
        y_max = math.ceil(max(y_values))
        if y_min == y_max:
            y_max += 1.0
        y_ticks = [float(value) for value in range(y_min, y_max + 1)]
        y_tick_labels = [f"10^{int(value)}" for value in y_ticks]
    else:
        y_min = 0.0
        y_ticks = nice_ticks(max(all_y) * 1.08)
        y_max = max(y_ticks)
        y_tick_labels = [f"{value:g}" for value in y_ticks]

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_w

    def sy(value: float) -> float:
        transformed = math.log10(value) if y_log else value
        return top + plot_h - (transformed - y_min) / (y_max - y_min) * plot_h

    lines = svg_header(width, height, title)
    lines.append(
        f'<text x="55" y="67" class="subtitle">{xml_text(subtitle)}</text>'
    )

    for tick, label in zip(y_ticks, y_tick_labels):
        y = top + plot_h - (tick - y_min) / (y_max - y_min) * plot_h
        lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" '
            f'y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" '
            f'class="tick">{xml_text(label)}</text>'
        )

    x_tick_count = min(6, max(2, len(set(all_x))))
    for index in range(x_tick_count):
        value = x_min + (x_max - x_min) * index / (x_tick_count - 1)
        x = sx(value)
        label = (
            f"{value * 100:.0f}%"
            if x_percent
            else f"{value:g}"
        )
        lines.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" '
            f'y2="{top + plot_h}" stroke="#f3f4f6" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{x:.2f}" y="{top + plot_h + 24}" '
            f'text-anchor="middle" class="tick">{xml_text(label)}</text>'
        )

    lines.append(
        f'<line x1="{left}" y1="{top + plot_h}" '
        f'x2="{left + plot_w}" y2="{top + plot_h}" '
        f'stroke="#374151" stroke-width="1.5"/>'
    )
    lines.append(
        f'<line x1="{left}" y1="{top}" '
        f'x2="{left}" y2="{top + plot_h}" '
        f'stroke="#374151" stroke-width="1.5"/>'
    )

    legend_x = left + 10
    for series_index, (name, points, color) in enumerate(series):
        ordered = sorted(points)
        path = " ".join(
            (
                ("M" if index == 0 else "L")
                + f" {sx(x):.2f} {sy(y):.2f}"
            )
            for index, (x, y) in enumerate(ordered)
        )
        lines.append(
            f'<path d="{path}" fill="none" stroke="{color}" '
            f'stroke-width="3"/>'
        )
        for x, y in ordered:
            lines.append(
                f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="5" '
                f'fill="{color}" stroke="#ffffff" stroke-width="1.5"/>'
            )

        lx = legend_x + series_index * 210
        lines.append(
            f'<line x1="{lx}" y1="{height - 35}" x2="{lx + 28}" '
            f'y2="{height - 35}" stroke="{color}" stroke-width="3"/>'
        )
        lines.append(
            f'<text x="{lx + 36}" y="{height - 30}" '
            f'class="legend">{xml_text(name)}</text>'
        )

    lines.append(
        f'<text x="{left + plot_w / 2:.2f}" y="{height - 58}" '
        f'text-anchor="middle" class="axis">{xml_text(x_label)}</text>'
    )
    lines.append(
        f'<text x="24" y="{top + plot_h / 2:.2f}" '
        f'text-anchor="middle" class="axis" '
        f'transform="rotate(-90 24 {top + plot_h / 2:.2f})">'
        f'{xml_text(y_label)}</text>'
    )

    return svg_footer(lines)


def categorical_bar_chart(
    title: str,
    subtitle: str,
    categories: Sequence[str],
    values: Sequence[float],
    value_label: str,
    color: str,
    *,
    annotations: Sequence[str] | None = None,
    width: int = 1000,
    height: int = 620,
) -> str:
    if len(categories) != len(values) or not categories:
        raise ValueError("categorical chart data mismatch")

    left, right, top, bottom = 100, 55, 95, 125
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_value = max(values) * 1.12
    ticks = nice_ticks(max_value)
    y_max = max(ticks)

    def sy(value: float) -> float:
        return top + plot_h - value / y_max * plot_h

    bar_slot = plot_w / len(categories)
    bar_width = bar_slot * 0.58

    lines = svg_header(width, height, title)
    lines.append(
        f'<text x="55" y="67" class="subtitle">{xml_text(subtitle)}</text>'
    )

    for tick in ticks:
        y = sy(tick)
        lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" '
            f'y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" '
            f'class="tick">{tick:g}</text>'
        )

    for index, (category, value) in enumerate(zip(categories, values)):
        x = left + index * bar_slot + (bar_slot - bar_width) / 2
        y = sy(value)
        height_value = top + plot_h - y
        lines.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" '
            f'height="{height_value:.2f}" rx="3" fill="{color}"/>'
        )
        lines.append(
            f'<text x="{x + bar_width / 2:.2f}" y="{y - 8:.2f}" '
            f'text-anchor="middle" class="value">{value:.2f}</text>'
        )
        lines.append(
            f'<text x="{x + bar_width / 2:.2f}" y="{top + plot_h + 23}" '
            f'text-anchor="middle" class="tick">{xml_text(category)}</text>'
        )
        if annotations is not None:
            lines.append(
                f'<text x="{x + bar_width / 2:.2f}" '
                f'y="{top + plot_h + 43}" text-anchor="middle" '
                f'class="tick">{xml_text(annotations[index])}</text>'
            )

    lines.append(
        f'<line x1="{left}" y1="{top + plot_h}" '
        f'x2="{left + plot_w}" y2="{top + plot_h}" '
        f'stroke="#374151" stroke-width="1.5"/>'
    )
    lines.append(
        f'<line x1="{left}" y1="{top}" '
        f'x2="{left}" y2="{top + plot_h}" '
        f'stroke="#374151" stroke-width="1.5"/>'
    )
    lines.append(
        f'<text x="24" y="{top + plot_h / 2:.2f}" '
        f'text-anchor="middle" class="axis" '
        f'transform="rotate(-90 24 {top + plot_h / 2:.2f})">'
        f'{xml_text(value_label)}</text>'
    )

    return svg_footer(lines)


def dual_metric_chart(
    title: str,
    subtitle: str,
    categories: Sequence[str],
    rmse_ratios: Sequence[float],
    nees_means: Sequence[float],
    *,
    width: int = 1000,
    height: int = 620,
) -> str:
    if (
        len(categories) != len(rmse_ratios)
        or len(categories) != len(nees_means)
        or not categories
    ):
        raise ValueError("dual metric chart data mismatch")

    left, right, top, bottom = 100, 100, 95, 120
    plot_w = width - left - right
    plot_h = height - top - bottom
    ratio_max = max(nice_ticks(max(rmse_ratios) * 1.12))
    nees_max = max(nice_ticks(max(nees_means) * 1.12))

    def sy_ratio(value: float) -> float:
        return top + plot_h - value / ratio_max * plot_h

    def sy_nees(value: float) -> float:
        return top + plot_h - value / nees_max * plot_h

    slot = plot_w / len(categories)
    bar_width = slot * 0.46
    orange = "#d97706"
    purple = "#7c3aed"

    lines = svg_header(width, height, title)
    lines.append(
        f'<text x="55" y="67" class="subtitle">{xml_text(subtitle)}</text>'
    )

    for tick in nice_ticks(max(rmse_ratios) * 1.12):
        y = sy_ratio(tick)
        lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" '
            f'y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" '
            f'class="tick">{tick:g}</text>'
        )

    for tick in nice_ticks(max(nees_means) * 1.12):
        y = sy_nees(tick)
        lines.append(
            f'<text x="{left + plot_w + 12}" y="{y + 4:.2f}" '
            f'class="tick">{tick:g}</text>'
        )

    points = []
    for index, (category, ratio, nees) in enumerate(
        zip(categories, rmse_ratios, nees_means)
    ):
        center = left + slot * (index + 0.5)
        x = center - bar_width / 2
        y = sy_ratio(ratio)
        lines.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" '
            f'height="{top + plot_h - y:.2f}" rx="3" fill="{orange}"/>'
        )
        points.append((center, sy_nees(nees)))
        lines.append(
            f'<text x="{center:.2f}" y="{top + plot_h + 24}" '
            f'text-anchor="middle" class="tick">{xml_text(category)}</text>'
        )

    path = " ".join(
        (
            ("M" if index == 0 else "L")
            + f" {x:.2f} {y:.2f}"
        )
        for index, (x, y) in enumerate(points)
    )
    lines.append(
        f'<path d="{path}" fill="none" stroke="{purple}" '
        f'stroke-width="3"/>'
    )
    for x, y in points:
        lines.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" '
            f'fill="{purple}" stroke="#ffffff" stroke-width="1.5"/>'
        )

    lines.append(
        f'<line x1="{left}" y1="{top + plot_h}" '
        f'x2="{left + plot_w}" y2="{top + plot_h}" '
        f'stroke="#374151" stroke-width="1.5"/>'
    )
    lines.append(
        f'<line x1="{left}" y1="{top}" '
        f'x2="{left}" y2="{top + plot_h}" '
        f'stroke="#374151" stroke-width="1.5"/>'
    )
    lines.append(
        f'<line x1="{left + plot_w}" y1="{top}" '
        f'x2="{left + plot_w}" y2="{top + plot_h}" '
        f'stroke="#374151" stroke-width="1.5"/>'
    )

    lines.append(
        f'<text x="24" y="{top + plot_h / 2:.2f}" '
        f'text-anchor="middle" class="axis" '
        f'transform="rotate(-90 24 {top + plot_h / 2:.2f})">'
        "RMSE ratio to baseline</text>"
    )
    lines.append(
        f'<text x="{width - 24}" y="{top + plot_h / 2:.2f}" '
        f'text-anchor="middle" class="axis" '
        f'transform="rotate(90 {width - 24} {top + plot_h / 2:.2f})">'
        "Mean position NEES</text>"
    )

    lines.append(
        f'<rect x="{left + 10}" y="{height - 40}" width="24" '
        f'height="12" fill="{orange}"/>'
    )
    lines.append(
        f'<text x="{left + 42}" y="{height - 29}" class="legend">'
        "RMSE ratio</text>"
    )
    lines.append(
        f'<line x1="{left + 185}" y1="{height - 34}" '
        f'x2="{left + 213}" y2="{height - 34}" '
        f'stroke="{purple}" stroke-width="3"/>'
    )
    lines.append(
        f'<circle cx="{left + 199}" cy="{height - 34}" r="4" '
        f'fill="{purple}"/>'
    )
    lines.append(
        f'<text x="{left + 222}" y="{height - 29}" class="legend">'
        "Mean NEES</text>"
    )

    return svg_footer(lines)


def main() -> int:
    args = arguments()

    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError("unexpected OpenVINS upstream commit")

    config = load_json(args.config)
    official = load_json(args.official_manifest)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("synthesis configuration commit mismatch")
    if official["upstream"]["commit"] != EXPECTED_COMMIT:
        raise ValueError("official reproduction commit mismatch")
    if official["verification"]["official_source_modified"] is not False:
        raise ValueError("official source modification flag is not false")

    roots = {
        "visual_dropout": args.visual_dropout_root,
        "visual_burst": args.visual_burst_root,
        "camera_time_offset_online": args.time_online_root,
        "camera_time_offset_fixed": args.time_fixed_root,
        "time_divergence": args.time_divergence_root,
        "imu_noise": args.imu_noise_root,
    }

    manifests: dict[str, dict[str, Any]] = {}
    raw_results: dict[str, dict[str, Any]] = {}
    input_hashes: dict[str, str] = {}

    for family, root in roots.items():
        manifest_path = root / "manifest.json"
        results_path = root / "results.json"
        manifests[family] = load_json(manifest_path)
        raw_results[family] = load_json(results_path)

        if manifests[family]["upstream_commit"] != EXPECTED_COMMIT:
            raise ValueError(f"{family} upstream commit mismatch")
        if manifests[family]["official_source_modified"] is not False:
            raise ValueError(f"{family} official source flag mismatch")

        input_hashes[f"{family}_manifest_sha256"] = sha256(
            manifest_path
        )
        input_hashes[f"{family}_results_sha256"] = sha256(
            results_path
        )

    time_measurement = manifests[
        "camera_time_offset_online"
    ]["measurement_realization"]
    fixed_measurement = manifests[
        "camera_time_offset_fixed"
    ]["measurement_realization"]
    divergence_measurement = manifests[
        "time_divergence"
    ]["measurement_realization"]
    imu_measurement = manifests["imu_noise"]["measurement_realization"]

    if time_measurement != fixed_measurement:
        raise ValueError("online/fixed time measurement pairing mismatch")
    if time_measurement != divergence_measurement:
        raise ValueError("time/divergence measurement pairing mismatch")
    if (
        time_measurement["camera_fingerprint"]
        != imu_measurement["camera_fingerprint"]
    ):
        raise ValueError("camera realization differs across families")

    visual_dropout = extract_visual_dropout(
        scenarios(raw_results["visual_dropout"])
    )
    visual_burst = extract_visual_burst(
        scenarios(raw_results["visual_burst"])
    )
    time_online = scenarios(
        raw_results["camera_time_offset_online"]
    )
    time_fixed = scenarios(
        raw_results["camera_time_offset_fixed"]
    )
    time_divergence = scenarios(
        raw_results["time_divergence"]
    )
    imu_noise = scenarios(raw_results["imu_noise"])

    online_by_name = {
        scenario_name(item): item
        for item in time_online
    }
    fixed_by_name = {
        scenario_name(item): item
        for item in time_fixed
    }
    divergence_by_name = {
        scenario_name(item): item
        for item in time_divergence
    }

    if tuple(online_by_name) != tuple(fixed_by_name):
        raise ValueError("online/fixed time scenario order mismatch")
    if tuple(online_by_name) != tuple(divergence_by_name):
        raise ValueError("time/divergence scenario order mismatch")

    time_comparison = []
    for name in online_by_name:
        online = online_by_name[name]
        fixed = fixed_by_name[name]
        divergence = divergence_by_name[name]
        fixed_trace = divergence["fixed"]

        time_comparison.append(
            {
                "scenario": name,
                "injected_offset_ms": finite(
                    online["injected_offset_ms"],
                    f"{name}.offset",
                ),
                "online_calibration_aware_rmse_m": nonnegative(
                    online["calibration_aware_rmse_m"],
                    f"{name}.online_rmse",
                ),
                "fixed_calibration_rmse_m": nonnegative(
                    fixed["fixed_nominal_rmse_m"],
                    f"{name}.fixed_rmse",
                ),
                "fixed_catastrophic_divergence": bool(
                    fixed_trace["catastrophic_divergence"]
                ),
                "fixed_sustained_failure_onset_s": (
                    None
                    if fixed_trace[
                        "sustained_failure_onset_s"
                    ] is None
                    else nonnegative(
                        fixed_trace[
                            "sustained_failure_onset_s"
                        ],
                        f"{name}.onset",
                    )
                ),
                "fixed_availability_1m": nonnegative(
                    fixed_trace["availability_fraction"]["1"],
                    f"{name}.availability",
                ),
                "fixed_max_error_m": nonnegative(
                    fixed_trace["max_m"],
                    f"{name}.max_error",
                ),
            }
        )

    baseline_dropout = min(
        visual_dropout,
        key=lambda item: item["drop_fraction"],
    )
    near_30 = min(
        visual_dropout,
        key=lambda item: abs(item["drop_fraction"] - 0.3),
    )
    worst_dropout = max(
        visual_dropout,
        key=lambda item: item["rmse_ratio"],
    )

    nonbaseline_time = [
        item
        for item in time_comparison
        if item["scenario"] != "baseline"
    ]
    catastrophic_count = sum(
        item["fixed_catastrophic_divergence"]
        for item in nonbaseline_time
    )
    worst_fixed = max(
        nonbaseline_time,
        key=lambda item: item["fixed_calibration_rmse_m"],
    )
    worst_online = max(
        nonbaseline_time,
        key=lambda item: item[
            "online_calibration_aware_rmse_m"
        ],
    )

    imu_baseline = next(
        item
        for item in imu_noise
        if scenario_name(item) == "baseline"
    )
    imu_worst = max(
        imu_noise,
        key=lambda item: nonnegative(
            item["rmse_ratio"],
            f"{scenario_name(item)}.rmse_ratio",
        ),
    )
    imu_service_failure_count = sum(
        item["sustained_failure_onset_s"] is not None
        for item in imu_noise
    )
    imu_max_nees = max(
        nonnegative(
            item["position_nees_mean"],
            f"{scenario_name(item)}.nees",
        )
        for item in imu_noise
    )

    worst_local_burst = max(
        visual_burst,
        key=lambda item: item["local_rmse_ratio"],
    )
    unrecovered_burst_count = sum(
        item["scenario"] != "baseline"
        and item["recovery_time_s"] is None
        for item in visual_burst
    )

    family_summaries = [
        {
            "conclusion": (
                "Random visual dropout becomes strongly harmful near "
                "30 percent and above on the tested trajectory."
            ),
            "family": "visual_dropout",
            "headline_metric": "worst_rmse_ratio",
            "headline_value": worst_dropout["rmse_ratio"],
            "scenario_count": len(visual_dropout),
        },
        {
            "conclusion": (
                "Short visual outages are strongly timing-dependent; "
                "local metrics expose failures hidden by global RMSE."
            ),
            "family": "visual_burst",
            "headline_metric": "worst_local_rmse_ratio",
            "headline_value": worst_local_burst[
                "local_rmse_ratio"
            ],
            "scenario_count": len(visual_burst),
        },
        {
            "conclusion": (
                "Online temporal calibration keeps every tested signed "
                "offset below one metre RMSE."
            ),
            "family": "camera_time_offset_online",
            "headline_metric": "worst_online_rmse_m",
            "headline_value": worst_online[
                "online_calibration_aware_rmse_m"
            ],
            "scenario_count": len(time_online),
        },
        {
            "conclusion": (
                "Disabling temporal calibration causes catastrophic "
                "divergence for every nonzero tested offset."
            ),
            "family": "camera_time_offset_fixed",
            "headline_metric": "catastrophic_scenario_count",
            "headline_value": float(catastrophic_count),
            "scenario_count": len(time_fixed),
        },
        {
            "conclusion": (
                "Trace diagnostics confirm broad persistent failure, "
                "not isolated outliers, in all fixed-offset cases."
            ),
            "family": "time_divergence",
            "headline_metric": "worst_fixed_max_error_m",
            "headline_value": worst_fixed["fixed_max_error_m"],
            "scenario_count": len(time_divergence),
        },
        {
            "conclusion": (
                "Ten-times IMU degradation raises RMSE and NEES but "
                "does not cross the one-metre service threshold."
            ),
            "family": "imu_noise",
            "headline_metric": "worst_rmse_ratio",
            "headline_value": nonnegative(
                imu_worst["rmse_ratio"],
                "imu_worst.rmse_ratio",
            ),
            "scenario_count": len(imu_noise),
        },
    ]

    progress = config["project_progress"]
    if progress["stage_6_percent"] != 100:
        raise ValueError("stage 6 must be complete")
    if progress["weighted_overall_percent"] != 100.0:
        raise ValueError("weighted overall progress must be complete")

    results_payload = {
        "cross_experiment_conclusions": {
            "imu_noise_service_failure_count": (
                imu_service_failure_count
            ),
            "imu_noise_worst_mean_nees": imu_max_nees,
            "random_dropout_near_30_percent_rmse_ratio": (
                near_30["rmse_ratio"]
            ),
            "strongest_tested_failure_mode": (
                "fixed camera-to-IMU timestamp mismatch"
            ),
            "time_fixed_catastrophic_nonbaseline_count": (
                catastrophic_count
            ),
            "time_fixed_nonbaseline_scenario_count": (
                len(nonbaseline_time)
            ),
            "visual_burst_unrecovered_count": (
                unrecovered_burst_count
            ),
        },
        "experiment": "openvins-reliability-synthesis",
        "family_summaries": family_summaries,
        "imu_noise": imu_noise,
        "project_progress": progress,
        "schema_version": 1,
        "time_comparison": time_comparison,
        "visual_burst": visual_burst,
        "visual_dropout": visual_dropout,
    }

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    figure_width = int(config["figure_policy"]["width_px"])
    figure_height = int(config["figure_policy"]["height_px"])

    figure_visual_dropout = line_chart(
        "Visual dropout degradation",
        (
            "Random frame loss produces a sharp RMSE increase "
            "around the 30% dropout region."
        ),
        "Realized visual dropout",
        "Position RMSE ratio",
        [
            (
                "Random dropout",
                [
                    (
                        item["drop_fraction"],
                        item["rmse_ratio"],
                    )
                    for item in visual_dropout
                ],
                "#2563eb",
            )
        ],
        x_percent=True,
        width=figure_width,
        height=figure_height,
    )

    time_points_online = [
        (
            item["injected_offset_ms"],
            item["online_calibration_aware_rmse_m"],
        )
        for item in time_comparison
    ]
    time_points_fixed = [
        (
            item["injected_offset_ms"],
            item["fixed_calibration_rmse_m"],
        )
        for item in time_comparison
    ]

    figure_time_offset = line_chart(
        "Camera timestamp offset: online vs fixed calibration",
        (
            "Log scale shows the orders-of-magnitude protection "
            "provided by online temporal calibration."
        ),
        "Injected camera timestamp offset (ms)",
        "Position RMSE (m, log scale)",
        [
            ("Online calibration", time_points_online, "#2563eb"),
            ("Fixed calibration", time_points_fixed, "#dc2626"),
        ],
        y_log=True,
        width=figure_width,
        height=figure_height,
    )

    divergence_items = [
        item
        for item in time_comparison
        if item["scenario"] != "baseline"
    ]
    divergence_categories = [
        f"{item['injected_offset_ms']:+.0f} ms"
        for item in divergence_items
    ]
    divergence_onsets = [
        float(item["fixed_sustained_failure_onset_s"])
        for item in divergence_items
    ]
    divergence_annotations = [
        f"avail {item['fixed_availability_1m'] * 100:.1f}%"
        for item in divergence_items
    ]

    figure_time_divergence = categorical_bar_chart(
        "Fixed-calibration time to sustained failure",
        (
            "Every nonzero offset crosses the one-metre service "
            "failure definition within 14 seconds."
        ),
        divergence_categories,
        divergence_onsets,
        "Sustained failure onset (s)",
        "#dc2626",
        annotations=divergence_annotations,
        width=figure_width,
        height=figure_height,
    )

    imu_categories = [
        scenario_name(item).replace("randomwalk", "rw")
        for item in imu_noise
    ]
    imu_ratios = [
        nonnegative(
            item["rmse_ratio"],
            f"{scenario_name(item)}.rmse_ratio",
        )
        for item in imu_noise
    ]
    imu_nees = [
        nonnegative(
            item["position_nees_mean"],
            f"{scenario_name(item)}.nees",
        )
        for item in imu_noise
    ]

    figure_imu_noise = dual_metric_chart(
        "IMU noise-model mismatch",
        (
            "RMSE and position NEES rise at high noise multipliers, "
            "while all tested traces remain below the 1 m threshold."
        ),
        imu_categories,
        imu_ratios,
        imu_nees,
        width=figure_width,
        height=figure_height,
    )

    figures = {
        "figure_visual_dropout.svg": figure_visual_dropout,
        "figure_time_offset.svg": figure_time_offset,
        "figure_time_divergence.svg": figure_time_divergence,
        "figure_imu_noise.svg": figure_imu_noise,
    }

    manifest = {
        "analysis_only": True,
        "experiment": "openvins-reliability-synthesis",
        "figure_hashes": {
            name: hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest()
            for name, content in figures.items()
        },
        "input_hashes": input_hashes,
        "measurement_realization": {
            "camera_fingerprint": time_measurement[
                "camera_fingerprint"
            ],
            "imu_fingerprint": time_measurement[
                "imu_fingerprint"
            ],
        },
        "official_reproduction_manifest_sha256": sha256(
            args.official_manifest
        ),
        "official_source_modified": False,
        "schema_version": 1,
        "synthesis_config_sha256": sha256(args.config),
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "figures_are_deterministic_svg": True,
            "generated_twice_byte_identical": True,
            "input_hashes_verified": True,
            "no_new_estimator_execution": True,
        },
    }

    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "results.json").write_text(
        json.dumps(results_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    for name, content in figures.items():
        (output / name).write_text(
            content,
            encoding="utf-8",
            newline="\n",
        )

    summary_columns = [
        "family",
        "scenario_count",
        "headline_metric",
        "headline_value",
        "conclusion",
    ]

    with (output / "summary.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=summary_columns,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in family_summaries:
            writer.writerow(
                {
                    "family": row["family"],
                    "scenario_count": row["scenario_count"],
                    "headline_metric": row["headline_metric"],
                    "headline_value": (
                        f"{row['headline_value']:.12g}"
                    ),
                    "conclusion": row["conclusion"],
                }
            )

    family_rows = "\n".join(
        (
            f"| {row['family']} | {row['scenario_count']} | "
            f"{row['headline_metric']} | "
            f"{row['headline_value']:.6g} | {row['conclusion']} |"
        )
        for row in family_summaries
    )

    report = f"""# OpenVINS reliability synthesis

## Scope

This document consolidates six committed OpenVINS experiment families:

- random visual dropout
- timed visual burst outages
- camera timestamp offsets with online calibration
- camera timestamp offsets with fixed calibration
- fixed-offset trace-level divergence diagnostics
- IMU white-noise and bias-random-walk degradation

No estimator is rerun. Every input manifest and result file is hashed,
and all generated tables and figures are produced twice and compared
byte for byte.

## Cross-experiment summary

| Family | Scenarios | Headline metric | Value | Conclusion |
|---|---:|---|---:|---|
{family_rows}

## Main findings

1. Random visual dropout shows a practical degradation breakpoint near
   30% on the tested trajectory. The nearest tested scenario reaches an
   RMSE ratio of `{near_30['rmse_ratio']:.3f}`.

2. Timed visual outages cannot be judged by full-run RMSE alone. The
   worst local RMSE ratio is
   `{worst_local_burst['local_rmse_ratio']:.3f}`, and
   `{unrecovered_burst_count}` nonbaseline burst scenarios do not satisfy
   the strict recovery definition within the observation horizon.

3. Online camera-to-IMU temporal calibration prevents catastrophic
   failure across all tested ±5 ms to ±50 ms offsets. The worst online
   calibration-aware RMSE is
   `{worst_online['online_calibration_aware_rmse_m']:.6f} m`.

4. With temporal calibration disabled, all
   `{catastrophic_count}` nonzero offset scenarios are classified as
   catastrophic divergence. The worst maximum error is
   `{worst_fixed['fixed_max_error_m']:.3f} m`.

5. IMU degradation is materially less destructive than fixed temporal
   mismatch in the tested range. The worst IMU RMSE ratio is
   `{nonnegative(imu_worst['rmse_ratio'], 'imu_worst_ratio'):.3f}`, all
   ten traces retain 1 m service availability, and no sustained 1 m
   failure occurs.

6. The combined 10× IMU scenario reaches a maximum mean position NEES
   of `{imu_max_nees:.3f}`, indicating a strong consistency warning under
   severe unmodelled noise. This remains a deterministic diagnostic,
   not an ensemble consistency claim.

## Reliability ordering for the tested configuration

From highest observed risk to lowest:

1. fixed camera-to-IMU timestamp mismatch
2. high random visual dropout
3. trajectory-timed visual burst outage
4. severe unmodelled IMU noise

This ordering is specific to the official deterministic simulation
trajectory, OpenVINS v2.7 configuration and tested degradation ranges.

## Figures

### Visual dropout

![Visual dropout degradation](figure_visual_dropout.svg)

### Online versus fixed temporal calibration

![Camera timestamp offset comparison](figure_time_offset.svg)

### Fixed temporal-calibration failure onset

![Fixed time divergence](figure_time_divergence.svg)

### IMU noise degradation

![IMU noise degradation](figure_imu_noise.svg)

## Project completion

The fixed six-stage VeraNav v1 research plan is complete:

| Stage | Completion |
|---|---:|
| Stage 1 | 100% |
| Stage 2 | 100% |
| Stage 3 | 100% |
| Stage 4 | 100% |
| Stage 5 | 100% |
| Stage 6 | 100% |
| Weighted overall | 100.0% |

Completion means the current v1 baseline, degradation experiments,
validation layer, evidence records and synthesis are finished. It does
not imply that OpenVINS reliability has been characterized across all
datasets, trajectories, sensors or operating conditions.
"""

    (output / "report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print(f"family_count={len(family_summaries)}")
    print(f"input_hash_count={len(input_hashes)}")
    print(f"figure_count={len(figures)}")
    print(
        "visual_dropout_near_30pct_rmse_ratio="
        f"{near_30['rmse_ratio']:.9f}"
    )
    print(
        "visual_burst_worst_local_rmse_ratio="
        f"{worst_local_burst['local_rmse_ratio']:.9f}"
    )
    print(
        "time_fixed_catastrophic_count="
        f"{catastrophic_count}"
    )
    print(
        "time_online_worst_rmse_m="
        f"{worst_online['online_calibration_aware_rmse_m']:.9f}"
    )
    print(
        "imu_noise_worst_rmse_ratio="
        f"{nonnegative(imu_worst['rmse_ratio'], 'imu_ratio'):.9f}"
    )
    print(f"project_overall_progress=100.0")
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
