# Scientific Validation Protocol

## Scope

WaveHolo Telescope is a synthetic, NumPy-based prototype for off-axis digital holography of a circular telescope pupil. This document defines what the project may claim, how results are validated, and which claims are prohibited.

## Validated claims

The project may claim only that its pipeline can, under the documented synthetic benchmark conditions:

- Propagate a modeled circular pupil using angular-spectrum methods with evanescent components removed.
- Model defocus, astigmatism, and coma Zernike aberrations.
- Form an ideal off-axis hologram with a horizontal tilted reference wave.
- Isolate a Fourier sideband and reconstruct a baseband complex field.
- Estimate pupil-to-sensor focus using aperture contrast.
- Report phase-quality diagnostics, including circular phase agreement, piston-removed wrapped-phase RMS, and secondary phase variance.
- Regenerate the documented benchmark and pass the regression suite.

Passing the smoke profile is an engineering acceptance check against
configured synthetic thresholds, not scientific acceptance. The scientific
profile remains insufficient until a genuinely frozen protocol and supporting
evidence exist; the criteria are not described as preregistered.

## Primary metrics

| Metric | Purpose | Required reporting |
|---|---|---|
| Focus bias | Difference between estimated and true focus distance | Value and sign |
| Focus resolution | Sampling or peak-width limit of the focus estimate | Value and method |
| Wavefront RMS | Residual phase error at the recovered focus | Waves RMS |
| Circular phase agreement | Global phase-pattern agreement | Dimensionless score |
| Null-control RMS | Reconstruction floor without a meaningful pupil signal | Waves RMS |
| Noise robustness | Metric stability under additive noise | Metric versus noise level |

## Required controls

Every scientific release must include or reference:

1. A null or empty-pupil control to establish the reconstruction floor.
2. An aberration-free pupil control to isolate the effect of modeled aberrations.
3. A noise sweep with fixed seed and repeated trials where stochasticity is present.
4. An ablation test for each major reconstruction stage where practical.
5. A clean-checkout reproduction run using the documented command.

## Uncertainty requirements

A result may be called robust only when its uncertainty or sensitivity is reported. At minimum, report:

- Sampling resolution of the focus metric.
- Sensitivity to the selected Fourier sideband width.
- Sensitivity to additive Gaussian noise.
- Variation across repeated runs when any stochastic component is used.

## Prohibited claims

Do not claim that this software demonstrates:

- Telescope, astronomical, or observational performance.
- Laboratory optical validation.
- Camera calibration, dark/flat correction, or a physical camera-noise model.
  Additive Gaussian intensity noise in the benchmark is synthetic only.
- Atmospheric-turbulence compensation.
- Holographic display performance.
- Quantum-computing or quantum-error-correction performance.
- Medical, safety-critical, or operational decision-making capability.

## Release interpretation

Synthetic benchmark results establish algorithm behavior under controlled assumptions. They do not establish performance on physical hardware or real astronomical data.

## Future work (not completed)

Physical camera and telescope validation, atmospheric turbulence,
adaptive-optics integration, and independent acquisition baselines are outside
the current scope. They require separate experimental protocols, data
provenance, and acceptance criteria; no completion or physical validation is
implied here.
