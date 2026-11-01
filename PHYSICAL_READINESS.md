# Physical-readiness plan

This repository is scientifically useful as a **synthetic reconstruction benchmark**. It is not yet validated as a telescope or camera instrument. The following sequence is the shortest defensible path from the current code to a physical experiment.

## 1. Freeze the optical geometry

Record, in SI units, the wavelength, camera pixel pitch (including any magnification), active sensor dimensions, pupil diameter at the reconstruction plane, sensor-to-pupil distance, reference-beam angle, reference intensity, exposure time, bit depth, and whether the camera applies offset subtraction, gain, gamma, binning, or demosaicing. The reconstruction must use the calibrated wavelength and effective pixel pitch; do not tune these to make a result look focused.

At 532 nm and 6.5 µm pixels, the Nyquist-limited angular spectrum is comfortably above the propagating band. The off-axis carrier must be chosen so that the +1 sideband, the -1 sideband, and the DC term do not overlap. In Fourier-bin units, verify `carrier > object_bandwidth + window_margin` and `carrier + window_margin <= N/2`. The package now rejects sideband windows that cannot fit in the centred spectrum, but the user must still verify that the sidebands are optically separated in the measured spectrum.

## 2. Calibrate before reconstruction

1. Acquire dark frames at the intended exposure and average them; estimate per-pixel read-noise variance.
2. Acquire flat-field frames with the reference and object blocked/unblocked as appropriate; estimate gain nonuniformity and saturation margin.
3. Measure the reference carrier from the Fourier transform of a blank-reference or weak-object hologram. The current implementation assumes a horizontal integer-bin carrier. For a real setup, record the carrier angle and fractional-bin location; fractional carriers should be implemented before claiming quantitative performance.
4. Measure the effective pixel pitch and magnification from a calibrated target or a known translation. A nominal camera pitch is not sufficient when relay optics are present.
5. Verify linearity over the planned intensity range and keep the camera below saturation. Store raw counts and calibration frames, not only display images.

## 3. Bench validation ladder

Run these tests in order, saving raw frames and metadata for every step:

- **Reference-only:** confirm the DC term and carrier are stable over time.
- **Known aperture, no aberration:** use a clean circular pupil or calibrated stop. Confirm the recovered amplitude support, energy scaling, and focus sweep.
- **Known phase object:** introduce a calibrated weak phase plate or deformable-mirror mode. Compare recovered phase after piston removal. Do not use Pearson correlation on wrapped phase.
- **Known defocus scan:** move the sensor or pupil by calibrated distances in both directions. Check that the focus score peaks at the independently measured position and that the peak is not at a sweep boundary.
- **Noise and exposure sweep:** repeat at multiple photon/read-noise levels. Report repeatability across independent frames, not only one noise realization.
- **Real telescope pupil:** add obstruction, spiders, segmentation, vignetting, atmospheric phase, and pupil misregistration to the mask/model before interpreting residuals.

## 4. Required acceptance report

For each dataset report the raw-frame identifiers, calibration version, optical parameters, sideband coordinates and crop, reconstruction distance grid, focus score curve, sampled and refined peak, whether the peak is at a boundary, repeatability across acquisitions, recovered wavefront with piston removed, mask definition and erosion, saturation fraction, and uncertainty budget. The `parabolic_peak` result is a local interpolation and sampling-resolution diagnostic; it is not a statistical confidence interval.

Minimum go/no-go thresholds should be set before looking at results. A sensible initial gate is: no saturated pixels in the analysis region, stable carrier position, a non-boundary focus peak, repeatability better than the claimed focus resolution, and a known-phase control whose residual is below the optical error budget. If the null-control floor is not measured, do not attribute residual phase to the telescope.

## 5. Known physical limitations

The current release uses a square grid, integer horizontal carrier, hard rectangular sideband crop, scalar monochromatic propagation, and a clean circular pupil. It does not model camera response, shot noise, read noise, pixel response, lens aberrations, finite source distance, atmospheric turbulence, polarization, reference drift, or fractional-bin carrier estimation. The hard crop low-passes the recovered phase and creates a measurable null-control floor.

Before a telescope claim, implement and validate: dark/flat correction, measured carrier estimation in two dimensions, apodized or model-based sideband filtering, non-square sensor support, camera noise likelihoods, pupil-registration estimation, and repeated-dataset uncertainty. Preserve the current synthetic tests as regression controls while adding recorded-data fixtures with permission and provenance.

## 6. Reproducibility command set

From the project root:

```sh
python3 tests/tests.py
python3 demo.py
python3 -m compileall -q src tests demo.py
```

The demo's bars are simulation results only. A successful run demonstrates numerical reproducibility, not physical instrument validity.
