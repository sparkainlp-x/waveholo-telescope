# waveholo-telescope v0.2.0

WaveHolo's off-axis digital holography pipeline, pointed at a
telescope pupil. A distant star through a circular pupil carrying
known Zernike aberrations is propagated to a sensor, recorded as
an off-axis hologram, and reconstructed: the pupil plane is found
by aperture contrast, and the wavefront at that plane is compared
against the injected aberration. NumPy only, AGPL-3.0-only.

Bench parameters are WaveHolo's own, kept deliberately so this adaptation is
comparable to the lab bench: wavelength 532 nm, pixel pitch 6.5 um, grid
256x256, carrier 80 bins, sideband half-width 48 bins, pupil-to-sensor distance
5.00 mm. Smaller documented numerical presets are 128:(40, 24) and
64:(20, 12), where each pair is (carrier, half-width). Other grids require
explicit carrier/window settings.

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

## Reproducible measurements

The benchmark records the real intensity hologram, adds deterministic
Gaussian noise with standard deviation relative to mean intensity, clips at
zero, and then reconstructs its complex baseband field. The benchmark reports
the full phase-variance sweep and determines localization, boundary status,
and error from the observed minimum; it does not assume a negative result.
Only current outputs produced by the commands below are evidence. The
Fourier-window fit check does not establish optical sideband separation.

### Freshly regenerated demo and smoke results

`python demo.py` (original 256×256 geometry): focus `5.138 mm` for a true
`5.000 mm` plane; wrapped wavefront RMS `0.0066` waves at measured focus
(`0.0064` at true focus); null-control RMS `0.0057` waves; 5% synthetic
intensity noise gave `5.129 mm` focus and `0.0070` waves RMS. The measured
phase-variance minimum was `10.000 mm`, at the sweep boundary, `+5.000 mm`
from true focus; it did not localize focus on this run.

The regenerated `waveholo-benchmark --config smoke` run (128×128, three
seeds, 5% primary noise) had median wrapped RMS `0.011407` waves against the
configured `0.010000` threshold, with `0/3` trials meeting it. Its synthetic
claim gate therefore **failed**; no positive claim is made. The measured
phase-variance minimum was `1.000 mm` from true focus in all three trials, so
the recorded decision was `does_not_locate_focus`. These smoke metrics are
engineering outputs, not physical or scientific validation.

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
python -m unittest discover -s tests -v
python demo.py
waveholo-benchmark --config smoke --output results/smoke
```

`worldholo-benchmark` remains an alias for compatibility. Packaged `smoke`
and `primary` presets are also available after wheel installation. The
smoke profile is an engineering check; a scientific profile remains
insufficient evidence until a genuinely frozen scientific protocol exists.

## Honest limits

- SYNTHETIC ONLY. No real telescope data has been run through
  this package, and nothing here is a claim about any real
  instrument, site, or adaptive-optics loop. The bars are
  ground-truth comparisons on simulated holograms.
- Focus sampling/refinement diagnostics (boundary, plateau, curvature and
  resolution) are not confidence intervals.
- The sideband window low-passes the wavefront: the recovered
  phase is the injected aberration smoothed by the window, and
  the pipeline floor (0.0057 waves) is the price.
- Piston is unobservable, tip/tilt are excluded, the pupil is an
  ideal disk. A real pupil (obstruction, spiders, segments,
  atmosphere) would need those terms added and re-measured.
- No physical camera/telescope validation, atmospheric turbulence,
  adaptive-optics integration, or independent acquisition baseline is
  included; these remain future work.

## Licence

AGPL-3.0-only. See `LICENSE`.

## Scientific-readiness additions

The package validates field shapes, finite camera values, physical
propagation parameters, integer carrier/window settings, and Fourier array
fit. The fixed 256x256 optical geometry remains unchanged. It exposes
`focus_sweep` and `parabolic_peak`; the latter supports irregular increasing
grids and reports boundary, plateau, curvature, and resolution diagnostics,
not a statistical confidence interval. Reported phase RMS is wrapped RMS in
waves after separate piston removal from recovered and injected phase.

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
