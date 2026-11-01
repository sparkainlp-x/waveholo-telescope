# waveholo-telescope v0.1.0

WaveHolo's off-axis digital holography pipeline, pointed at a
telescope pupil. A distant star through a circular pupil carrying
known Zernike aberrations is propagated to a sensor, recorded as
an off-axis hologram, and reconstructed: the pupil plane is found
by aperture contrast, and the wavefront at that plane is compared
against the injected aberration. NumPy only, AGPL-3.0-only.

Bench parameters are WaveHolo's own, kept deliberately so this
adaptation is comparable to the lab bench: wavelength 532 nm,
pixel pitch 6.5 um, grid 256x256, carrier 80 bins, sideband
half-width 48 bins, pupil-to-sensor distance 5.00 mm.

## Geometry

The pupil field is P = A * exp(i phi): A is 1 inside a disk of
radius 64 px and 0 outside, phi is a Zernike sum in waves
(defocus 0.4, astigmatism-x 0.3, coma-x 0.2 in the demo). The star
is at infinity, so the incident field is a plane wave and the
pupil itself is the object. Piston is excluded (unobservable in a
hologram) and tip/tilt are excluded (pointing, absorbed by
sideband centering); no spider vanes, central obstruction, or
segmentation -- a clean circular pupil, so the bars measure the
pipeline, not a particular telescope.

## Pipeline

Identical to waveholo v0.1.5: angular-spectrum propagation
(evanescent components dropped), hologram H = |U + R|^2 with a
reference tilted along x, sideband crop in Fourier space shifted
to baseband, back-propagation sweep. Two metrics differ, because
a pupil is a PHASE object and the lab bench's metrics assume an
amplitude object:

- aperture_contrast (focus metric, MAXIMAL at focus): at the true
  pupil plane the amplitude IS the disk, so (mean |U|^2 inside -
  mean |U|^2 outside) / (inside + outside) peaks there: 1 for a
  perfect disk, 0 when inside and outside carry equal intensity.
- phase_agreement (wavefront metric): |mean phasor of the wrapped
  recovered-minus-injected phase difference| inside an eroded
  mask (2 px, because the hard aperture edge is blurred by the
  sideband window). 1 is perfect, 0 is random.

## Measured bars (demo.py, 256x256)

- T1 focus: aperture-contrast peak 5.138 mm, error +0.138 mm
  against the true 5.00 mm -- but the contrast at the true plane
  is 0.9976 against a peak of 0.9976 (difference 0.0000 to four
  decimals). The peak is FLAT-TOPPED: on this geometry the metric
  locates the pupil plane only to ~±0.25 mm (the sweep step), not
  better. That is a property of the metric, not a calibration
  error, and it costs almost nothing: see T2.
- T2 wavefront at the measured focus: RMS error 0.0066 waves,
  agreement 0.9991 (eroded mask, 2 px; piston removed). At the true
  plane the RMS is 0.0064 waves -- the ±0.25 mm focus uncertainty
  costs 0.0002 waves.
- T3 null control (no aberrations, true plane): RMS error
  0.0057 waves. That is the pipeline floor (sideband windowing
  plus discretization): the T2 error is essentially the floor,
  not aberration-dependent error.
- T4 noise (Gaussian noise, std 5% of mean hologram, clipped at
  zero like a real sensor): focus 5.129 mm (error +0.129 mm),
  wavefront RMS 0.0070 waves, agreement 0.9990. Noise barely
  degrades anything at this level.
- T5 secondary readout: WaveHolo's phase_variance minimum on the
  same sweep sits at the 10.000 mm sweep EDGE (value 0.7514) --
  no interior dip at the pupil plane. On telescope pupil data the
  candidate universal metric does NOT locate focus. This is a
  measured negative, kept, not a footnote: phase_variance assumes
  a near-uniform phase at focus, and a pupil's aberration phase
  is genuinely non-uniform there.

## Two corrections made during the build

- A first demo run reported a Pearson correlation of 0.9529
  alongside an RMS error of 0.0066 waves. That 0.9529 was a seam
  artifact: Pearson on wrapped phases counts the +-0.5 wave seam
  as anti-correlation even when the wrapped difference is tiny.
  It is not reported as a result anywhere; phase_agreement (the
  circular statistic) replaces it.
- The first aperture_contrast normalization divided by the
  overall mean intensity, giving values above 1 (5.07). The
  metric now divides by inside + outside, bounded in [-1, 1].

## Run it

```sh
python3 demo.py          # bars T1-T5 (256x256, seconds)
python3 tests/tests.py   # 13 tests, from the package root (128x128)
```

## Honest limits

- SYNTHETIC ONLY. No real telescope data has been run through
  this package, and nothing here is a claim about any real
  instrument, site, or adaptive-optics loop. The bars are
  ground-truth comparisons on simulated holograms.
- The focus location is coarse (~±0.25 mm on this geometry) for
  the flat-top reason above; the wavefront itself is recovered
  far more precisely (0.0066 waves) because it is insensitive to
  that focus error.
- The sideband window low-passes the wavefront: the recovered
  phase is the injected aberration smoothed by the window, and
  the pipeline floor (0.0057 waves) is the price.
- Piston is unobservable, tip/tilt are excluded, the pupil is an
  ideal disk. A real pupil (obstruction, spiders, segments,
  atmosphere) would need those terms added and re-measured.
- Authorship: Brisson only. No other author's code or paradigm
  is contained in this package.

## Licence

AGPL-3.0-only. See `LICENSE`.

## Scientific-readiness additions

The package now validates field shapes, finite camera values, physical
propagation parameters, integer carrier/window settings, and Fourier
sideband fit. It also exposes `focus_sweep` and `parabolic_peak` for
reusable focus analysis. `parabolic_peak` reports boundary status and a
sampling-resolution diagnostic; its refinement is not a statistical
confidence interval.

The project remains synthetic-only. Before using camera or telescope data,
follow `PHYSICAL_READINESS.md`, which specifies calibration, sideband
separation checks, bench validation, acceptance reporting, and limitations
that must be addressed before an instrument claim.

## Documentation

- [Technical documentation](docs/TECHNICAL_DOCUMENTATION.md): mathematical
  model, numerical conventions, processing flow, validation, reproducibility,
  and laboratory transition plan.
- [API reference](docs/API_REFERENCE.md): public constants, functions,
  parameters, return values, validation behavior, and examples.
- [Physical-readiness plan](PHYSICAL_READINESS.md): calibration and bench
  validation protocol before using recorded camera or telescope data.
