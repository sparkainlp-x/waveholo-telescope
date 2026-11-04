# Changelog

## Unreleased focused repair (2026-11-04)

- Route reconstructed complex baseband through benchmark measurement; add
  known-field, consumption and deliberately incorrect intensity controls.
- Share validated acceptance thresholds and explicitly name the primary
  noise condition; distinguish coarse-prior refinement from blind acquisition.
- Fail closed on invalid claims, counts and inputs; separate engineering
  acceptance from unverified scientific evidence and preserve negative results.
- Validate statistical reference cases and correct the documented equal-group
  independent two-proportion power formula; BH ordering remains unchanged.
- Use strict JSON and schema 2.0 with JSON-null missing diagnostics, installed
  package provenance, packaged presets and exact wheel/sdist smoke validation.
- Preserve historical artifacts and demo bars as prior findings, not evidence
  for the repaired benchmark. Smoke still fails the unchanged 0.01-wave target.
- Attribute overlapping repair patterns from PR #2 and #4 and evidence-scope
  guidance from #3 in `REPRODUCIBILITY.md`; no PR was merged.

## Unreleased scientific-readiness pass

- Added explicit validation for square fields, finite holograms, physical
  propagation parameters, integer carrier/window settings, and sideband fit.
- Added reusable `focus_sweep` and `parabolic_peak` helpers. The latter
  reports boundary status and sampling resolution so a flat or edge peak is
  not over-interpreted as a precise focus measurement.
- Added regression tests for the new safeguards and a laboratory validation
  protocol in `PHYSICAL_READINESS.md`.

## v0.1.0 (2026-10-31)

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
