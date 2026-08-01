# Changelog

All notable changes to VeraNav are documented in this file.

## 0.1.0 development milestone — 2026-08-01

### Added

- explicit NED, FRD, quaternion, perturbation, and error-state conventions
- quaternion and rotation utilities
- immutable nominal state and IMU samples
- midpoint nominal IMU propagation
- continuous ESKF error dynamics
- Van Loan covariance discretization
- GNSS position measurement and Joseph covariance update
- right-error injection and attitude covariance reset
- NIS and NEES consistency metrics
- deterministic circular trajectory, IMU, and GNSS simulation
- structured GNSS outage and position-bias degradation
- Monte Carlo failure analysis and fixed-grid reliability envelopes
- paired common-random-number comparison
- percentile bootstrap and Wilson confidence intervals
- adaptive reliability-boundary search
- deterministic JSON, CSV, Markdown, and SVG reports
- unit, numerical, reproducibility, and continuous-integration checks

### Scope

This milestone is a synthetic verification framework. It is not a real-world benchmark, integrity-certified navigation system, or safety-critical product.

## KF-GINS official demo reproduction

- Added WGS84 ECEF and anchor-centred NED conversion utilities.
- Added an audited KF-GINS result importer with safe zero-week inference.
- Added duplicate truth timestamp consolidation and spatial-radius rejection.
- Added deterministic JSON, CSV and Markdown reproduction evidence.
- Added geodesy and KF-GINS integration tests.
