# KF-GINS official demonstration reproduction

VeraNav reproduces the official KF-GINS demonstration at upstream commit `8291a93e49de513fe9d21f819500d39082ded611` in an external GPL-licensed checkout. The Apache-licensed VeraNav repository stores only the independently written importer, tests, compact metrics and provenance records.

The official navigation result stores GPS week as zero while the truth file stores GPS week 2017. VeraNav infers the unique reference week only when the estimate week is uniformly zero, the reference week is unique and nonzero, and both files have an overlapping seconds-of-week interval. Other week mismatches are rejected.

The truth file contains consecutive duplicate timestamps. VeraNav consolidates only exactly equal consecutive timestamps, uses arithmetic means for latitude and height, a circular mean for longitude, and rejects any duplicate group whose ECEF radius exceeds 5 m. The manifest records all normalization diagnostics and source hashes.

Run the importer with:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/import_kf_gins.py \
  --estimate /path/to/KF_GINS_Navresult.nav \
  --reference /path/to/truth.nav \
  --imu /path/to/Leador-A15.txt \
  --gnss /path/to/GNSS-RTK.txt \
  --config /path/to/kf-gins.yaml \
  --output-dir outputs/kf_gins \
  --upstream-commit 8291a93e49de513fe9d21f819500d39082ded611 \
  --source-archive-sha256 6ca9032ad344bb635c74fb9d142c65da0a5fed92a2d2e8e028fb58c2e8d15f42
```

The compact output consists of `manifest.json`, `metrics.json`, `metrics.csv` and `report.md`. Official source code, raw data, build products and full trajectories remain outside this repository.
