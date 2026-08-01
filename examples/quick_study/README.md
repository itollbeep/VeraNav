# VeraNav quick-study example

This directory contains the deterministic outputs of:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_reliability_study.py \
  --quick \
  --seeds 8 \
  --output-dir examples/quick_study
```

The two SVG files displayed from the repository README are rendered with:

```bash
PYTHONPATH=src .venv/bin/python scripts/render_study_svg.py \
  examples/quick_study/study.json \
  docs/assets
```

Files:

- `study.json`: complete paired comparison and adaptive-boundary record
- `paired_comparison.csv`: seed-wise baseline and degraded metrics
- `adaptive_boundary.csv`: one reliability-boundary row per outage duration
- `report.md`: concise human-readable summary

The example is intentionally small so that continuous integration and local verification remain fast. It is a method demonstration, not a real-world benchmark or safety result.
