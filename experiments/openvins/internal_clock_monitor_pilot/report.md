# V2-E03 internal clock monitor pilot

- status: `monitor_not_supported`
- static false-positive scenarios: `0/6`
- early-warning positives detected: `0/2`
- early-warning positives with positive lead: `0/2`
- secondary dynamic scenarios detected: `3/22`

## Monitor boundary

The online monitor used only estimator timestamps and estimated camera-to-IMU offset history. Injected clock offset and physical trajectory reference were excluded from threshold calibration and alert generation.

## Thresholds

- estimated_offset_velocity_rms: `0.174480025166` (static maximum `0.158618204696`)
- estimated_offset_acceleration_rms: `2.37733248366` (static maximum `2.16121134878`)
- estimated_offset_peak_to_peak: `0.147296731228` (static maximum `0.133906119298`)

## Primary early-warning cases

- `sinusoidalslow-span05-drop00`: alert `None`, degradation `204.29980516433716`, lead `None` s
- `sinusoidalslow-span05-drop10`: alert `None`, degradation `206.6998028755188`, lead `None` s

## Claim boundary

This is a single-trajectory monitor pilot calibrated on six static controls from the same evidence family. It does not establish a multi-trajectory false-alarm rate or deployment readiness.
