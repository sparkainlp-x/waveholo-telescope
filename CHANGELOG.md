# Changelog

## Unreleased scientific-readiness pass

- Corrected benchmark sensor noise to modify the real recorded intensity
  before sideband reconstruction, and regenerated evidence is required.
- Added validated grid presets and explicit unknown-grid carrier/window
  settings while retaining the original 256x256 geometry.
- Recorded full phase-variance sweeps and measured localization decisions;
  made smoke and scientific claim profiles distinct and removed
  preregistration language.
- Hardened focus/statistical inputs, JSON serialization, installed-source
  provenance and bounded transfer-function caching.
- Corrected the two-proportion power approximation to its documented
  equal-group, two-sided independent-sample design and added a reference
  sample-size check.
- Bumped the benchmark artifact/config schema to 1.1 for measured
  phase-variance assessment fields.
- Added packaged CLI presets, the `waveholo-benchmark` command, and isolated
  wheel-install CI while retaining `worldholo-benchmark`.
- Updated version metadata and documented physical validation, turbulence,
  adaptive optics and independent acquisition as future work.
- Added explicit validation for square fields, finite holograms, physical
  propagation parameters, integer carrier/window settings, and sideband fit.
- Added reusable `focus_sweep` and `parabolic_peak` helpers. The latter
  reports boundary status and sampling resolution so a flat or edge peak is
  not over-interpreted as a precise focus measurement.
- Added regression tests for the new safeguards and a laboratory validation
  protocol in `PHYSICAL_READINESS.md`.

## v0.1.0 (2026-10-31)

> Historical measurements below predate the audited intensity-noise correction
> and are not current benchmark evidence. Regenerate results with the current
> version before citing quantitative performance.

- Standalone telescope adaptation of WaveHolo's off-axis digital
  holography pipeline: circular pupil (radius 64 px) with Zernike
  aberrations (defocus, astigmatism, coma; piston and tip/tilt
  excluded, stated), angular-spectrum propagation at WaveHolo's
  bench parameters (532 nm, 6.5 um, 256x256, carrier 80 bins,
  window 48 bins), hologram H = |U + R|^2, sideband
  reconstruction, back-propagation sweep. New metrics:
  aperture_contrast (maximal at the pupil plane) and
  phase_agreement (circular statistic; Pearson on wrapped phases
  was caught giving a seam artifact and is not used). Measured:
  focus 5.138 mm vs true 5.00 mm (flat-topped peak, ~±0.25 mm
  location); wavefront RMS 0.0066 waves, agreement 0.9991; null
  floor 0.0057 waves; 5% hologram noise barely degrades anything;
  WaveHolo's phase_variance does NOT locate the pupil plane
  (minimum at the 10.00 mm sweep edge). Synthetic only; no real
  telescope claim.
