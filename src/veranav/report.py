"""Deterministic JSON, CSV and Markdown export for reliability studies."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from veranav.boundary import ReliabilityBoundary
from veranav.comparison import PairedComparison


@dataclass(frozen=True, slots=True, eq=False)
class StudyReport:
    """Serializable paired comparison and adaptive reliability boundary."""

    title: str
    comparison_name: str
    comparison: PairedComparison
    boundary: ReliabilityBoundary

    def __post_init__(self) -> None:
        title = str(self.title).strip()
        comparison_name = str(self.comparison_name).strip()
        if not title:
            raise ValueError("title must not be empty")
        if not comparison_name:
            raise ValueError("comparison_name must not be empty")
        if not isinstance(self.comparison, PairedComparison):
            raise TypeError("comparison must be a PairedComparison")
        if not isinstance(self.boundary, ReliabilityBoundary):
            raise TypeError("boundary must be a ReliabilityBoundary")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "comparison_name", comparison_name)


def _interval_dict(interval: Any) -> dict[str, Any]:
    result = {
        "estimate": interval.estimate,
        "lower": interval.lower,
        "upper": interval.upper,
        "confidence": interval.confidence,
    }
    if hasattr(interval, "resamples"):
        result["resamples"] = interval.resamples
        result["seed"] = interval.seed
    return result


def study_report_dict(report: StudyReport) -> dict[str, Any]:
    """Convert a study report into built-in Python types."""
    if not isinstance(report, StudyReport):
        raise TypeError("report must be a StudyReport")
    comparison = report.comparison
    boundary_rows = []
    for point in report.boundary.points:
        boundary_rows.append(
            {
                "outage_duration_s": point.outage_duration_s,
                "status": point.status,
                "lower_reliable_bias_m": point.lower_reliable_bias_m,
                "upper_unreliable_bias_m": point.upper_unreliable_bias_m,
                "bracket_width_m": point.bracket_width_m,
                "evaluation_count": len(point.evaluations),
                "evaluations": [
                    {
                        "bias_magnitude_m": item.bias_magnitude_m,
                        "divergence_rate": item.summary.divergence_rate,
                        "divergence_interval": _interval_dict(
                            item.divergence_interval
                        ),
                        "reliable": item.reliable,
                    }
                    for item in point.evaluations
                ],
            }
        )
    return {
        "schema_version": 1,
        "title": report.title,
        "comparison_name": report.comparison_name,
        "paired_comparison": {
            "seeds": list(comparison.seeds),
            "baseline_failure_rate": comparison.baseline_failure_rate,
            "degraded_failure_rate": comparison.degraded_failure_rate,
            "degraded_only_failure_count": comparison.degraded_only_failure_count,
            "recovered_failure_count": comparison.recovered_failure_count,
            "rmse_worsening_probability": comparison.rmse_worsening_probability,
            "rmse_difference_interval_m": _interval_dict(
                comparison.rmse_difference_interval_m
            ),
            "maximum_error_difference_interval_m": _interval_dict(
                comparison.maximum_error_difference_interval_m
            ),
            "runs": [
                {
                    "seed": seed,
                    "baseline_position_rmse_m": baseline.position_rmse_m,
                    "degraded_position_rmse_m": degraded.position_rmse_m,
                    "rmse_difference_m": rmse_delta,
                    "baseline_position_max_m": baseline.position_max_m,
                    "degraded_position_max_m": degraded.position_max_m,
                    "maximum_error_difference_m": maximum_delta,
                    "baseline_failed": bool(baseline_failed),
                    "degraded_failed": bool(degraded_failed),
                }
                for (
                    seed,
                    baseline,
                    degraded,
                    rmse_delta,
                    maximum_delta,
                    baseline_failed,
                    degraded_failed,
                ) in zip(
                    comparison.seeds,
                    comparison.baseline_metrics,
                    comparison.degraded_metrics,
                    comparison.rmse_differences_m,
                    comparison.maximum_error_differences_m,
                    comparison.baseline_failures,
                    comparison.degraded_failures,
                    strict=True,
                )
            ],
        },
        "adaptive_boundary": {
            "max_bias_m": report.boundary.max_bias_m,
            "tolerance_m": report.boundary.tolerance_m,
            "requirement": {
                "max_divergence_rate": report.boundary.requirement.max_divergence_rate,
                "confidence": report.boundary.requirement.confidence,
                "use_upper_confidence_bound": (
                    report.boundary.requirement.use_upper_confidence_bound
                ),
            },
            "points": boundary_rows,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_comparison_csv(path: Path, payload: dict[str, Any]) -> None:
    rows = payload["paired_comparison"]["runs"]
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_boundary_csv(path: Path, payload: dict[str, Any]) -> None:
    rows = []
    for point in payload["adaptive_boundary"]["points"]:
        rows.append(
            {
                "outage_duration_s": point["outage_duration_s"],
                "status": point["status"],
                "lower_reliable_bias_m": point["lower_reliable_bias_m"],
                "upper_unreliable_bias_m": point["upper_unreliable_bias_m"],
                "bracket_width_m": point["bracket_width_m"],
                "evaluation_count": point["evaluation_count"],
            }
        )
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    scalar = float(value)
    if not math.isfinite(scalar):
        raise ValueError("report values must be finite")
    return f"{scalar:.6f}"


def _write_markdown(path: Path, report: StudyReport) -> None:
    comparison = report.comparison
    lines = [
        f"# {report.title}",
        "",
        "## Paired comparison",
        "",
        f"Scenario: {report.comparison_name}",
        "",
        f"Seeds: {len(comparison.seeds)}",
        "",
        (
            "Mean RMSE difference, degraded minus baseline: "
            f"{comparison.rmse_difference_interval_m.estimate:.6f} m "
            f"[{comparison.rmse_difference_interval_m.lower:.6f}, "
            f"{comparison.rmse_difference_interval_m.upper:.6f}]"
        ),
        "",
        (
            "Mean maximum-error difference, degraded minus baseline: "
            f"{comparison.maximum_error_difference_interval_m.estimate:.6f} m "
            f"[{comparison.maximum_error_difference_interval_m.lower:.6f}, "
            f"{comparison.maximum_error_difference_interval_m.upper:.6f}]"
        ),
        "",
        f"Baseline failure rate: {comparison.baseline_failure_rate:.6f}",
        "",
        f"Degraded failure rate: {comparison.degraded_failure_rate:.6f}",
        "",
        "## Adaptive reliability boundary",
        "",
        "| Outage (s) | Status | Reliable lower bias (m) | Unreliable upper bias (m) | Width (m) | Evaluations |",
        "|---:|:---|---:|---:|---:|---:|",
    ]
    for point in report.boundary.points:
        lines.append(
            "| "
            + " | ".join(
                [
                    _format_number(point.outage_duration_s),
                    point.status,
                    _format_number(point.lower_reliable_bias_m),
                    _format_number(point.upper_unreliable_bias_m),
                    _format_number(point.bracket_width_m),
                    str(len(point.evaluations)),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            "All baseline and degraded runs use paired random seeds. Confidence intervals and boundary evaluations are deterministic for the recorded seed sequences.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_study_report(
    report: StudyReport,
    output_directory: str | Path,
) -> tuple[Path, Path, Path, Path]:
    """Write deterministic JSON, two CSV tables and a Markdown summary."""
    if not isinstance(report, StudyReport):
        raise TypeError("report must be a StudyReport")
    directory = Path(output_directory)
    if directory.exists() and not directory.is_dir():
        raise ValueError("output_directory must be a directory path")
    directory.mkdir(parents=True, exist_ok=True)
    payload = study_report_dict(report)
    json_path = directory / "study.json"
    comparison_path = directory / "paired_comparison.csv"
    boundary_path = directory / "adaptive_boundary.csv"
    markdown_path = directory / "report.md"
    _write_json(json_path, payload)
    _write_comparison_csv(comparison_path, payload)
    _write_boundary_csv(boundary_path, payload)
    _write_markdown(markdown_path, report)
    return json_path, comparison_path, boundary_path, markdown_path


__all__ = ["StudyReport", "study_report_dict", "write_study_report"]
