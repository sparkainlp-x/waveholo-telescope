# Metrics

All reported errors include the condition, protocol, N, and uncertainty.
Pupil-domain errors exclude pixels outside the declared pupil and apply only the
predeclared piston removal. Current code implements lower-order demo metrics; full
factorial export is UNRUN.

| Metric | Definition | Units / interpretation | Implementation |
|---|---|---|---|
| Residual RMS wavefront error | `sqrt(mean((wrap(φrec−φtrue))²))` over valid pupil | Report radians, waves at λ, and OPD nm | `metrics.py:phase_rms_error` (currently waves) |
| Zernike coefficient RMSE | `sqrt(mean((ĉj−cj)²))` over fitted modes | Waves; requires implemented basis fit | Not implemented |
| Per-mode coefficient error | `ĉj−cj` for each mode ID | Waves; mode convention must be named | Not implemented |
| Relative wavefront error | residual RMS / injected RMS | Dimensionless; undefined for zero aberration | Benchmark layer |
| Focus-estimation error | `zselected−ztrue` and absolute value | metres | `analysis.py:parabolic_peak` |
| Strehl ratio | `exp(−σφ²)` only under valid small-error/statistical assumptions | Dimensionless; otherwise not reported | Not currently implemented |
| Pupil-sampling error | Error against oversampled reference after fixed resampling | pixels or waves; explicit baseline required | Not implemented |
| Robustness degradation | Metric at noise/sampling condition minus matched noiseless baseline | Report units and paired uncertainty | Benchmark layer |
| Runtime / memory | Wall time and process peak RSS | seconds / bytes; machine dependent | Benchmark layer |
| Effect size and interval | Paired mean/median difference plus bootstrap interval | Metric units and 95% interval | `statistics.py` has paired bootstrap utility |

With an orthonormal Zernike basis and identical weighting/domain, wavefront RMSE
equals coefficient RMSE by Parseval. The current implemented polynomial terms are
not claimed as a fully normalized complete Zernike basis, so that equivalence must
not be assumed until normalization and fitting tests are added. [17][18][30]

## Unit conversions

For phase RMS `σ_rad`: `σ_waves = σ_rad/(2π)`. For wavelength `λ_nm`,
`OPD_nm = σ_waves × λ_nm`. Do not quote waves without wavelength; do not compare
wavefront error across different wavelengths without the declared conversion.

References numbered [17], [18], [30] require complete bibliographic mapping before
publication and are presently placeholders, not verified references.
