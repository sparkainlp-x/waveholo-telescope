# Limitations and failure modes

- No real telescope data have been analyzed.
- No atmospheric-turbulence model has been validated.
- The current pupil is an ideal unobstructed disk; it omits spiders, segmentation,
  central obstruction, registration error, and vignetting.
- The current low-order polynomial subset does not span all non-modal aberrations
  and is not a complete radial-order 2–10 orthonormal basis.
- Pupil sampling limits resolvable spatial modes; aliasing thresholds are not yet
  measured by the required factorial study.
- The current benchmark helper implements only relative additive Gaussian noise;
  photon and read-noise models are not yet complete.
- The sideband filter blurs the pupil edge and contributes a numerical error floor.
- Focus contrast has a flat peak; interpolation diagnostics are not confidence
  intervals.
- No adaptive-optics control loop or observational/operational performance is
  demonstrated.
