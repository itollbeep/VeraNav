"""Adaptive one-dimensional reliability-boundary search by outage duration."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable, Literal

from veranav.degradation import GnssDegradation
from veranav.experiment import ExperimentConfig
from veranav.monte_carlo import FailureCriteria, MonteCarloSummary, run_monte_carlo
from veranav.statistics import ConfidenceInterval, wilson_score_interval

BoundaryStatus = Literal["bounded", "all_reliable", "none_reliable"]


def _nonnegative_levels(values: Iterable[float], name: str) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if not result:
        raise ValueError(f"{name} must not be empty")
    if any(not math.isfinite(value) or value < 0.0 for value in result):
        raise ValueError(f"{name} must contain finite nonnegative values")
    if tuple(sorted(set(result))) != result:
        raise ValueError(f"{name} must be strictly increasing without duplicates")
    return result


def _seed_tuple(values: Iterable[int]) -> tuple[int, ...]:
    result = tuple(values)
    if not result or len(set(result)) != len(result):
        raise ValueError("seeds must be nonempty and unique")
    if any(
        not isinstance(seed, int) or isinstance(seed, bool) or seed < 0
        for seed in result
    ):
        raise ValueError("seeds must be nonnegative integers")
    return result


@dataclass(frozen=True, slots=True, eq=False)
class ReliabilityRequirement:
    """Summary-level requirement for declaring one degradation point reliable."""

    max_divergence_rate: float = 0.0
    confidence: float = 0.95
    use_upper_confidence_bound: bool = False

    def __post_init__(self) -> None:
        rate = float(self.max_divergence_rate)
        confidence = float(self.confidence)
        if not math.isfinite(rate) or not 0.0 <= rate <= 1.0:
            raise ValueError("max_divergence_rate must be between zero and one")
        if not math.isfinite(confidence) or not 0.0 < confidence < 1.0:
            raise ValueError("confidence must be strictly between zero and one")
        if not isinstance(self.use_upper_confidence_bound, bool):
            raise TypeError("use_upper_confidence_bound must be a bool")
        object.__setattr__(self, "max_divergence_rate", rate)
        object.__setattr__(self, "confidence", confidence)

    def classify(
        self,
        summary: MonteCarloSummary,
    ) -> tuple[bool, ConfidenceInterval]:
        if not isinstance(summary, MonteCarloSummary):
            raise TypeError("summary must be a MonteCarloSummary")
        trials = len(summary.seeds)
        failures = int(round(summary.divergence_rate * trials))
        interval = wilson_score_interval(failures, trials, self.confidence)
        value = interval.upper if self.use_upper_confidence_bound else summary.divergence_rate
        return value <= self.max_divergence_rate, interval


@dataclass(frozen=True, slots=True, eq=False)
class BoundaryEvaluation:
    """One evaluated bias level during an adaptive boundary search."""

    bias_magnitude_m: float
    summary: MonteCarloSummary
    divergence_interval: ConfidenceInterval
    reliable: bool

    def __post_init__(self) -> None:
        bias = float(self.bias_magnitude_m)
        if not math.isfinite(bias) or bias < 0.0:
            raise ValueError("bias_magnitude_m must be finite and nonnegative")
        if not isinstance(self.summary, MonteCarloSummary):
            raise TypeError("summary must be a MonteCarloSummary")
        if not isinstance(self.divergence_interval, ConfidenceInterval):
            raise TypeError("divergence_interval must be a ConfidenceInterval")
        if not isinstance(self.reliable, bool):
            raise TypeError("reliable must be a bool")
        if not math.isclose(
            self.divergence_interval.estimate,
            self.summary.divergence_rate,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("divergence interval estimate must match the summary")
        object.__setattr__(self, "bias_magnitude_m", bias)


@dataclass(frozen=True, slots=True, eq=False)
class ReliabilityBoundaryPoint:
    """Reliable-to-unreliable bias bracket for one outage duration."""

    outage_duration_s: float
    status: BoundaryStatus
    lower_reliable_bias_m: float | None
    upper_unreliable_bias_m: float | None
    evaluations: tuple[BoundaryEvaluation, ...]

    def __post_init__(self) -> None:
        outage = float(self.outage_duration_s)
        if not math.isfinite(outage) or outage < 0.0:
            raise ValueError("outage_duration_s must be finite and nonnegative")
        if self.status not in ("bounded", "all_reliable", "none_reliable"):
            raise ValueError("invalid boundary status")
        if not self.evaluations:
            raise ValueError("evaluations must not be empty")
        biases = tuple(item.bias_magnitude_m for item in self.evaluations)
        if tuple(sorted(set(biases))) != biases:
            raise ValueError("evaluations must be strictly ordered by bias")
        for name in ("lower_reliable_bias_m", "upper_unreliable_bias_m"):
            value = getattr(self, name)
            if value is not None:
                scalar = float(value)
                if not math.isfinite(scalar) or scalar < 0.0:
                    raise ValueError(f"{name} must be None or finite and nonnegative")
                object.__setattr__(self, name, scalar)
        if self.status == "bounded":
            if self.lower_reliable_bias_m is None or self.upper_unreliable_bias_m is None:
                raise ValueError("bounded points require both bracket values")
            if self.lower_reliable_bias_m >= self.upper_unreliable_bias_m:
                raise ValueError("bounded bracket must have positive width")
        elif self.status == "all_reliable":
            if self.lower_reliable_bias_m is None or self.upper_unreliable_bias_m is not None:
                raise ValueError("all_reliable requires only a lower bound")
        else:
            if self.lower_reliable_bias_m is not None or self.upper_unreliable_bias_m is None:
                raise ValueError("none_reliable requires only an upper bound")
        object.__setattr__(self, "outage_duration_s", outage)

    @property
    def bracket_width_m(self) -> float | None:
        if self.status != "bounded":
            return None
        assert self.lower_reliable_bias_m is not None
        assert self.upper_unreliable_bias_m is not None
        return self.upper_unreliable_bias_m - self.lower_reliable_bias_m


@dataclass(frozen=True, slots=True, eq=False)
class ReliabilityBoundary:
    """Adaptive bias reliability boundary over increasing outage durations."""

    points: tuple[ReliabilityBoundaryPoint, ...]
    max_bias_m: float
    tolerance_m: float
    requirement: ReliabilityRequirement

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError("points must not be empty")
        outages = tuple(point.outage_duration_s for point in self.points)
        if tuple(sorted(set(outages))) != outages:
            raise ValueError("boundary points must use increasing unique outages")
        for name in ("max_bias_m", "tolerance_m"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and strictly positive")
            object.__setattr__(self, name, value)
        if not isinstance(self.requirement, ReliabilityRequirement):
            raise TypeError("requirement must be a ReliabilityRequirement")

    def midpoint_boundary_m(self) -> tuple[float | None, ...]:
        values: list[float | None] = []
        for point in self.points:
            if point.status == "bounded":
                assert point.lower_reliable_bias_m is not None
                assert point.upper_unreliable_bias_m is not None
                values.append(
                    0.5 * (
                        point.lower_reliable_bias_m
                        + point.upper_unreliable_bias_m
                    )
                )
            elif point.status == "all_reliable":
                values.append(point.lower_reliable_bias_m)
            else:
                values.append(None)
        return tuple(values)


def search_reliability_boundary(
    base_config: ExperimentConfig,
    outage_durations_s: Iterable[float],
    seeds: Iterable[int],
    *,
    fault_start_s: float,
    max_bias_m: float,
    tolerance_m: float = 0.25,
    max_iterations: int = 16,
    criteria: FailureCriteria = FailureCriteria(),
    requirement: ReliabilityRequirement = ReliabilityRequirement(),
) -> ReliabilityBoundary:
    """Bracket the reliable bias limit with deterministic bisection."""
    if not isinstance(base_config, ExperimentConfig):
        raise TypeError("base_config must be an ExperimentConfig")
    if not isinstance(criteria, FailureCriteria):
        raise TypeError("criteria must be a FailureCriteria")
    if not isinstance(requirement, ReliabilityRequirement):
        raise TypeError("requirement must be a ReliabilityRequirement")
    outages = _nonnegative_levels(outage_durations_s, "outage_durations_s")
    seed_values = _seed_tuple(seeds)
    start = float(fault_start_s)
    maximum = float(max_bias_m)
    tolerance = float(tolerance_m)
    if not math.isfinite(start) or not 0.0 <= start <= base_config.trajectory.duration_s:
        raise ValueError("fault_start_s must lie within the trajectory duration")
    if not math.isfinite(maximum) or maximum <= 0.0:
        raise ValueError("max_bias_m must be finite and strictly positive")
    if not math.isfinite(tolerance) or not 0.0 < tolerance < maximum:
        raise ValueError("tolerance_m must lie strictly between zero and max_bias_m")
    if (
        not isinstance(max_iterations, int)
        or isinstance(max_iterations, bool)
        or max_iterations < 1
    ):
        raise ValueError("max_iterations must be a positive integer")

    remaining = base_config.trajectory.duration_s - start + base_config.trajectory.imu_dt
    points = []

    for outage in outages:
        cache: dict[float, BoundaryEvaluation] = {}

        def evaluate(bias: float) -> BoundaryEvaluation:
            key = float(bias)
            if key not in cache:
                degradation = GnssDegradation(
                    outage_start_s=start if outage > 0.0 else None,
                    outage_duration_s=outage,
                    bias_start_s=start if key > 0.0 else None,
                    bias_duration_s=remaining if key > 0.0 else 0.0,
                    bias_n=[key, 0.0, 0.0],
                )
                config = replace(base_config, degradation=degradation)
                summary = run_monte_carlo(config, seed_values, criteria)
                reliable, interval = requirement.classify(summary)
                cache[key] = BoundaryEvaluation(
                    bias_magnitude_m=key,
                    summary=summary,
                    divergence_interval=interval,
                    reliable=reliable,
                )
            return cache[key]

        low = 0.0
        high = maximum
        low_result = evaluate(low)
        if not low_result.reliable:
            point = ReliabilityBoundaryPoint(
                outage_duration_s=outage,
                status="none_reliable",
                lower_reliable_bias_m=None,
                upper_unreliable_bias_m=0.0,
                evaluations=tuple(cache[key] for key in sorted(cache)),
            )
            points.append(point)
            continue

        high_result = evaluate(high)
        if high_result.reliable:
            point = ReliabilityBoundaryPoint(
                outage_duration_s=outage,
                status="all_reliable",
                lower_reliable_bias_m=maximum,
                upper_unreliable_bias_m=None,
                evaluations=tuple(cache[key] for key in sorted(cache)),
            )
            points.append(point)
            continue

        for _ in range(max_iterations):
            if high - low <= tolerance:
                break
            midpoint = 0.5 * (low + high)
            if evaluate(midpoint).reliable:
                low = midpoint
            else:
                high = midpoint

        points.append(
            ReliabilityBoundaryPoint(
                outage_duration_s=outage,
                status="bounded",
                lower_reliable_bias_m=low,
                upper_unreliable_bias_m=high,
                evaluations=tuple(cache[key] for key in sorted(cache)),
            )
        )

    return ReliabilityBoundary(
        points=tuple(points),
        max_bias_m=maximum,
        tolerance_m=tolerance,
        requirement=requirement,
    )


__all__ = [
    "BoundaryEvaluation",
    "ReliabilityBoundary",
    "ReliabilityBoundaryPoint",
    "ReliabilityRequirement",
    "search_reliability_boundary",
]
