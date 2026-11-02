# waveholo-telescope technical documentation

**Version:** 0.2.0
**Status:** synthetic reconstruction benchmark; not telescope-validated  
**License:** AGPL-3.0-only  
**Language:** Python 3 with NumPy

## 1. Scope and scientific status

`waveholo-telescope` is a compact, NumPy-only implementation of an off-axis digital holography pipeline aimed at recovering a telescope pupil field. It simulates a distant star illuminating a circular pupil with known Zernike aberrations, propagates the complex field to a sensor, records an intensity hologram with a tilted reference wave, reconstructs the object sideband, back-propagates through candidate distances, and evaluates the recovered pupil wavefront.

The current project is a **synthetic ground-truth benchmark**. Its numerical bars measure agreement between a simulated injected field and a reconstructed field. They are not measurements of a real telescope, camera, observing site, or adaptive-optics system. The included physical-readiness protocol describes the calibration and validation work required before experimental claims.

## 2. Design goals

The implementation is intentionally small and auditable. Its main goals are:

1. Keep the propagation and hologram equations explicit.
2. Make the pupil-plane focus criterion appropriate for a phase-bearing telescope pupil.
3. Compare recovered phase using circular statistics rather than linear statistics on wrapped phase.
4. Make the synthetic result reproducible with fixed geometry and deterministic tests.
5. Fail early when array shapes or physical parameters are invalid.
6. Expose enough metadata and diagnostics for a later laboratory implementation.

The package does not attempt to provide a complete camera-control stack, telescope control system, atmospheric reconstructor, or general-purpose holographic phase-unwrapping framework.

## 3. Mathematical model

### 3.1 Coordinate grid and pupil

For an `N × N` array and pupil radius `R` pixels, the normalized pupil coordinates are

\[
\rho(x,y) = \frac{\sqrt{(x-N/2)^2+(y-N/2)^2}}{R},
\]

\[
\theta(x,y) = \operatorname{atan2}(y-N/2, x-N/2).
\]

The circular aperture support is

\[
A(x,y) = \begin{cases}1,&\rho\leq 1\\0,&\rho>1.\end{cases}
\]

The complex pupil field is

\[
P(x,y) = A(x,y)\exp\left[i2\pi\phi(x,y)\right],
\]

where `phi` is expressed in waves, not radians.

The implemented phase basis is:

\[
\phi = c_d(2\rho^2-1)
+ c_{a_x}\rho^2\cos(2\theta)
+ c_{a_y}\rho^2\sin(2\theta)
\]

\[
+ c_{c_x}(3\rho^3-2\rho)\cos(\theta)
+ c_{c_y}(3\rho^3-2\rho)\sin(\theta).
\]

These correspond to defocus, two astigmatism orientations, and two coma orientations. The basis is evaluated everywhere for convenience, but the field and ground-truth comparisons are valid only inside the pupil support.

Piston is not included in the aberration model. The recovered phase is compared after piston removal because an absolute global phase is not identifiable from the intended measurement without an external phase reference. Tip/tilt is also excluded from the benchmark because it represents pointing or pupil displacement and is normally handled as a separate registration variable.

### 3.2 Angular-spectrum propagation

Propagation over distance `z` uses the sampled angular-spectrum transfer function:

\[
U_z = \mathcal{F}^{-1}\left\{\mathcal{F}\{U_0\}H_z(f_x,f_y)\right\},
\]

with

\[
H_z = \exp\left[i k z\sqrt{1-(\lambda f_x)^2-(\lambda f_y)^2}\right],
\quad k=\frac{2\pi}{\lambda}.
\]

Spatial frequencies are generated with `numpy.fft.fftfreq`. Components with

\[
1-(\lambda f_x)^2-(\lambda f_y)^2\leq0
\]

are set to zero as evanescent components. For propagating components the transfer function has unit modulus, so the discrete propagation is energy-preserving apart from the removed evanescent content and floating-point error. Negative `z` performs numerical back-propagation.

The default synthetic bench parameters are:

| Parameter | Value |
|---|---:|
| Grid size | `256 × 256` |
| Pixel pitch | `6.5 µm` |
| Wavelength | `532 nm` |
| Carrier | `80` Fourier bins |
| Sideband half-width | `48` bins |
| Pupil radius | `64` pixels in the demo |
| Pupil-to-sensor distance | `5.00 mm` |

The physical sampling pitch must be the **effective** pitch at the modeled plane, including relay magnification. A nominal camera pixel pitch is not automatically the correct `dx` after optics.

The documented numerical presets are `(grid, carrier, half-width) = (256, 80, 48), (128, 40, 24), (64, 20, 12)`. Other grid sizes require explicit carrier and window settings. The implementation checks Fourier-array fit only; it does not claim that a sideband is separated from DC and its conjugate.

### 3.3 Off-axis hologram recording

The sensor field `U` is mixed with a unit-amplitude reference tilted along the x direction:

\[
R(x,y)=\exp\left[i2\pi\frac{c x}{N}\right],
\]

where `c` is the integer carrier in Fourier bins. The ideal noiseless camera measurement is

\[
H(x,y)=|U(x,y)+R(x,y)|^2.
\]

The intensity is non-negative by construction. The DC term, object autocorrelation term, and two cross-correlation sidebands appear in the Fourier transform of `H`.

### 3.4 Sideband reconstruction

The reconstruction performs the following operations:

1. Convert the hologram to a 2-D Fourier spectrum with `fft2` and `fftshift`.
2. Select the sideband centered at `(row=N/2, column=N/2-carrier)`.
3. Crop a square window with half-width `win`.
4. Shift the crop to the centered baseband location by placing it back into an `N × N` zero-filled spectrum.
5. Apply `ifftshift` and `ifft2` to obtain the reconstructed complex field.

The filter is a hard rectangular crop. It therefore limits spatial bandwidth, blurs sharp pupil edges, and contributes to the measured null-control phase floor. Sensor noise is added to the recorded real intensity hologram relative to its mean intensity, clipped at zero, and only then reconstructed. The sideband must be separated from the DC and conjugate sideband in the actual camera spectrum; passing array-fit validation alone does not prove optical separation.

The current implementation assumes a square sensor, a horizontal integer-bin carrier, and a carrier sign convention consistent with `record_hologram`. Fractional-bin or arbitrary-angle carriers are not yet estimated automatically.

### 3.5 Focus metric

For a telescope pupil, the object is not a uniform real-amplitude object: its phase intentionally varies across the aperture. A metric that expects phase uniformity can therefore fail at the true pupil plane. The primary focus metric is aperture contrast:

\[
C = \frac{\langle |U|^2\rangle_{\mathrm{inside}}-
\langle |U|^2\rangle_{\mathrm{outside}}}
{\langle |U|^2\rangle_{\mathrm{inside}}+
\langle |U|^2\rangle_{\mathrm{outside}}}.
\]

The score is bounded by `[-1, 1]` when intensities are finite and non-negative. A clean, correctly focused pupil approaches `1` because energy is concentrated inside the known support. The focus sweep evaluates this score after back-propagating to candidate distances.

`phase_variance` is retained as a secondary diagnostic only. It is an intensity-weighted circular variance of the whole field and assumes that a low-variance phase is desirable. The benchmark records it at every sweep distance, reports the measured minimum and boundary status, and decides localization by comparing the sampled minimum with synthetic true focus and half the minimum sweep interval. The historical negative result is retained only when the current sweep reproduces it.

### 3.6 Wavefront metrics

Recovered and reference phases are represented in waves. Both recovered and true phases have their circular piston removed independently; this is not relative-piston alignment. The residual is wrapped to `[-0.5, 0.5)` waves before calculating:

- `phase_rms_error`: root-mean-square wrapped residual in waves (wrapped RMS).
- `phase_agreement`: magnitude of the mean residual phasor, from `0` for random residuals to `1` for perfect circular agreement.

A linear Pearson correlation is deliberately not used for wrapped phase. A small physical residual crossing the `-0.5/+0.5` representation seam can appear as a large linear anticorrelation despite excellent circular agreement.

The demo evaluates the wavefront on a mask eroded by two pixels to avoid interpreting the blurred hard-aperture edge as interior wavefront error. Focus curvature and half-step resolution are sampling diagnostics, not confidence intervals. Quadratic refinement accepts irregular strictly increasing grids, flags boundaries, plateaus, and weak curvature, and emits JSON-safe `null` when unavailable.

## 4. End-to-end processing flow

The synthetic demo follows this sequence:

```text
Zernike coefficients + circular pupil
                 │
                 ▼
        complex pupil field P
                 │ angular_spectrum(+Z_TRUE)
                 ▼
         complex sensor field U
                 │ record_hologram
                 ▼
             intensity H
                 │ record real intensity H
                 │ additive Gaussian noise relative to mean intensity + clipping
                 │ reconstruct_field
                 ▼
       baseband complex sensor field
                 │ for each candidate distance d:
                 │ angular_spectrum(-d)
                 ▼
        candidate pupil reconstruction
                 │ aperture_contrast
                 ▼
             focus curve
                 │ parabolic_peak (optional)
                 ▼
      selected focus and resolution diagnostic
                 │ phase_rms_error / phase_agreement
                 ▼
          recovered wavefront quality
```

The demo and benchmark use the same intensity-noise helper. The reusable `focus_sweep` and `parabolic_peak` functions expose the same analysis for downstream applications.

## 5. Reproducible benchmark

From the project root:

```sh
python -m unittest discover -s tests -v
python demo.py
waveholo-benchmark --config smoke --output results/smoke
```

`worldholo-benchmark` is retained as a compatibility alias. The smoke profile
is a software/engineering check against configured synthetic thresholds, not
scientific acceptance. The scientific profile reports insufficient evidence
until a genuinely frozen protocol and supporting evidence are available.
Corrected output must be regenerated with the commands above; historical
pre-correction benchmark numbers are not reused.

The freshly regenerated `python demo.py` output on the original 256×256
geometry gave a `5.138 mm` focus estimate (true `5.000 mm`), wrapped RMS
`0.0066` waves at measured focus (`0.0064` at true focus), null-control RMS
`0.0057` waves, and `0.0070` waves after 5% synthetic intensity noise. The
phase-variance minimum was at the `10.000 mm` boundary, `+5.000 mm` from true
focus, so the negative localization result was reproduced for that sweep.
The smoke preset produced median RMS `0.011407` waves against a `0.010000`
threshold with `0/3` successes; its claim gate correctly reported `fail`.

## 6. Input and data conventions

- Arrays are NumPy arrays and must be square 2-D arrays where required.
- Complex fields use the usual NumPy convention with real and imaginary parts in arbitrary but consistent amplitude units.
- Holograms are real-valued intensity arrays. Values must be finite for reconstruction.
- Distances, wavelength, and pixel pitch are in metres.
- Pupil radius and erosion are in pixels.
- Zernike coefficients and phase errors are in waves.
- Carrier and sideband half-width are integer Fourier-bin parameters.
- The package does not attach calibration metadata to arrays. Applications should store the complete optical and camera configuration alongside every dataset.

## 7. Validation and failure modes

The implementation raises `ValueError` for non-square fields, non-finite holograms, invalid propagation parameters, invalid integer carrier/window settings, sideband windows that cannot fit in the centered spectrum, incompatible metric shapes, empty metric masks, and invalid erosion parameters.

A valid array-fit check does not validate the physics. Before analyzing camera data, independently verify carrier separation, camera linearity, saturation margin, dark/flat correction, effective pixel pitch, wavelength, pupil registration, and sensor-to-pupil distance.

The focus result should be treated as low confidence when:

- the maximum lies on the sweep boundary;
- the metric curve is flat compared with repeatability noise;
- the sideband overlaps DC or its conjugate;
- the pupil mask is misregistered;
- the camera is clipped or non-linear;
- the null-control floor is comparable to the claimed signal.

`parabolic_peak` fits an interior local quadratic, including for irregular
strictly increasing grids, and reports boundary, plateau, weak-curvature,
and half-step sampling diagnostics. These are not statistical confidence
intervals; unavailable values serialize as JSON `null`.

The power-analysis helper estimates equal per-group size for an independent,
two-sided two-proportion comparison with pooled null variance and alternative
variance. For `p_null=0.05`, `p_alternative=0.15`, `alpha=0.05`, and power
`0.8`, its normal approximation returns 141 per group. It is an approximation,
not observed benchmark evidence.

## 8. Physical laboratory transition

The complete bench-to-telescope sequence is in [`PHYSICAL_READINESS.md`](../PHYSICAL_READINESS.md). The required order is:

1. Freeze the optical geometry and effective sampling.
2. Acquire dark and flat-field calibration data.
3. Measure the 2-D carrier from the recorded spectrum.
4. Validate the reference-only and known-aperture cases.
5. Validate focus with an independently measured translation.
6. Validate phase with a known phase object or deformable-mirror mode.
7. Repeat over exposure and noise levels.
8. Add real pupil obscurations, spiders, segmentation, vignetting, and atmosphere to the model before interpreting telescope data.
9. Report raw-frame identifiers, calibration versions, sideband coordinates, focus curves, masks, saturation, repeatability, and uncertainty.

Physical camera/telescope validation, atmospheric turbulence, adaptive-optics
integration, and independent acquisition baselines remain future work and are
not asserted complete. Other engineering extensions include dark/flat
correction, arbitrary-angle fractional-bin carrier estimation, apodized or
model-based sideband filtering, physical camera noise likelihoods,
pupil-registration estimation, and repeated-dataset uncertainty analysis.

## 9. Package structure

```text
waveholo-telescope/
├── src/waveholo_telescope/
│   ├── __init__.py       Public package exports and version
│   ├── analysis.py       Focus sweeps and parabolic peak diagnostics
│   ├── hologram.py       Recording and sideband reconstruction
│   ├── benchmark.py      Synthetic benchmark engine and CLI
│   ├── metrics.py        Focus and phase metrics
│   ├── propagation.py    Angular-spectrum propagation
│   └── pupil.py          Grid, circular pupil, and Zernike phase model
├── tests/tests.py        NumPy/unittest regression suite
├── demo.py               Reproducible synthetic T1–T5 benchmark
├── PHYSICAL_READINESS.md Laboratory validation plan
├── API_REFERENCE.md      Public API reference
├── README.md             Short project overview
├── CHANGELOG.md          Version history
├── CITATION.cff          Citation metadata
├── LICENSE               AGPL-3.0-only license
└── pyproject.toml        Build and dependency metadata
```

## 10. Citation and contribution

Use the repository's `CITATION.cff` for citation metadata. Contributions that change numerical behavior should include a regression test, a before/after benchmark when relevant, and an explicit statement of whether the change affects synthetic interpretation or physical readiness. Do not present synthetic bars as instrument measurements.
