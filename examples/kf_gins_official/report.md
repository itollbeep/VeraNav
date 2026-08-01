# KF-GINS official demo reproduction

- Upstream commit: `8291a93e49de513fe9d21f819500d39082ded611`
- Evaluation samples: 672959
- Evaluation duration: 3361.982000 s
- 3D position RMSE: 0.015251 m
- Mean 3D position error: 0.013282 m
- 95th percentile 3D error: 0.026220 m
- Maximum 3D position error: 0.123503 m

The official result stores GPS week as zero. VeraNav infers the unique nonzero reference week only when both trajectories have a valid seconds-of-week overlap. Consecutive duplicate truth timestamps are consolidated with an audited spatial-radius limit.
