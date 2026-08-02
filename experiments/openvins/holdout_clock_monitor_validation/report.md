# V2-E04 holdout clock monitor validation

- status: `holdout_monitor_supported`
- static false positives: `0/6`
- primary challenges degradation eligible: `4/4`
- primary challenges detected: `4/4`
- primary positive lead: `4/4`
- dynamic coverage: `21/24`

## Frozen monitor

- channel: `estimated_offset_peak_to_peak`
- threshold: `0.14729673122826897 ms`
- persistence: `3.0 s`
- causal window: `5.0 s`

## Primary challenges

- `holdout-sinusoidal-phase025-span05-drop00`: alert `13.799986839294434`, degradation `102.89990186691284`, lead `89.09991502761841`
- `holdout-sinusoidal-phase025-span05-drop10`: alert `13.199987411499023`, degradation `102.49990224838257`, lead `89.29991483688354`
- `holdout-sinusoidal-phase050-span05-drop00`: alert `13.199987411499023`, degradation `194.09981489181519`, lead `180.89982748031616`
- `holdout-sinusoidal-phase050-span05-drop10`: alert `13.199987411499023`, degradation `192.09981679916382`, lead `178.8998293876648`

## Claim boundary

This is perturbation-holdout validation on one official trajectory. It does not establish multi-trajectory or real-world deployment performance.
