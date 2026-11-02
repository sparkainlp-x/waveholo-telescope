# waveholo-telescope API reference

This reference documents the public Python API in version 0.2.0. Import from `waveholo_telescope` for the stable top-level functions and constants, or from the named submodules when working with implementation-specific organization.

```python
import waveholo_telescope as wh
```

## Installation and import

From a checkout:

```sh
python3 -m pip install .
```

The only runtime dependency is NumPy. For a source checkout without installation:

```sh
PYTHONPATH=src python3 -c "import waveholo_telescope as wh; print(wh.__version__)"
```

## Package metadata

### `waveholo_telescope.__version__`

Current package version string: `"0.2.0"`.

## Public constants

| Name | Value | Meaning |
|---|---:|---|
| `N` | `256` | Default square simulation grid size |
| `DX` | `6.5e-6` | Default sampling pitch in metres |
| `WL` | `532e-9` | Default wavelength in metres |
| `CAR_DEFAULT` | `80` | Default horizontal carrier in Fourier bins |
| `WIN_DEFAULT` | `48` | Default sideband half-width in Fourier bins |

These constants reproduce the synthetic bench configuration. Real camera use requires measured effective values.

## `waveholo_telescope.propagation`

### `angular_spectrum(field, z, dx=DX, wl=WL)`

Propagate a square complex field using the sampled angular-spectrum method.

**Parameters**

- `field`: square 2-D array-like, converted to complex NumPy dtype.
- `z`: finite propagation distance in metres. Negative values back-propagate.
- `dx`: positive finite sample pitch in metres.
- `wl`: positive finite wavelength in metres.

**Returns**

A square complex NumPy array with the same shape as `field`.

**Raises**

`ValueError` if `field` is not square 2-D, contains non-finite values, `z` is non-finite, or `dx`/`wl` is not positive and finite.

**Numerical behavior**

The transfer function is cached by `(z, n, dx, wl)`. Propagating components are multiplied by a unit-modulus phase factor. Evanescent components are set to zero. The implementation uses NumPy's FFT normalization, so a positive and negative distance round trip is numerically reversible for the retained propagating spectrum.

**Example**

```python
from waveholo_telescope import angular_spectrum

sensor_field = angular_spectrum(pupil_field, 5.0e-3)
recovered_pupil = angular_spectrum(sensor_field, -5.0e-3)
```

## `waveholo_telescope.pupil`

### `pupil_grid(n, radius)`

Construct normalized polar coordinates and a circular pupil mask.

**Parameters**

- `n`: integer array dimension.
- `radius`: pupil radius in pixels.

**Returns**

`(rho, theta, mask)`:

- `rho`: `n × n` normalized radial coordinate array.
- `theta`: `n × n` azimuth array in radians.
- `mask`: Boolean disk support where `rho <= 1`.

The coordinate center is at `(n//2, n//2)`. The function does not currently validate `n` or `radius`; callers should supply a positive integer grid and positive radius.

### `zernike_phase(rho, theta, defocus=0.0, astig_x=0.0, astig_y=0.0, coma_x=0.0, coma_y=0.0)`

Evaluate the implemented low-order aberration basis in waves.

**Parameters**

- `rho`, `theta`: matching arrays, normally from `pupil_grid`.
- `defocus`: coefficient of `2*rho**2 - 1`.
- `astig_x`: coefficient of `rho**2*cos(2*theta)`.
- `astig_y`: coefficient of `rho**2*sin(2*theta)`.
- `coma_x`: coefficient of `(3*rho**3 - 2*rho)*cos(theta)`.
- `coma_y`: coefficient of `(3*rho**3 - 2*rho)*sin(theta)`.

All coefficients are in waves. The result is also in waves. No piston or tip/tilt term is included. Values outside the pupil are returned mathematically but should be ignored using the pupil mask.

### `pupil_field(n, radius, **aberrations)`

Construct a unit-amplitude circular pupil carrying the requested phase.

**Parameters**

- `n`: grid dimension.
- `radius`: radius in pixels.
- `**aberrations`: keyword arguments accepted by `zernike_phase`.

**Returns**

`(field, mask, phase_waves)`:

- `field`: complex `n × n` array, zero outside the disk and `exp(2j*pi*phase)` inside.
- `mask`: Boolean pupil support.
- `phase_waves`: injected phase array in waves, intended for comparison inside `mask`.

**Example**

```python
from waveholo_telescope import pupil_field

field, mask, true_phase = pupil_field(
    256, 64, defocus=0.4, astig_x=0.3, coma_x=0.2
)
```

## `waveholo_telescope.hologram`

### `record_hologram(sensor_field, car=CAR_DEFAULT)`

Record an ideal off-axis intensity hologram with a unit-amplitude horizontal reference.

**Parameters**

- `sensor_field`: square 2-D complex sensor field.
- `car`: integer carrier, in Fourier bins. Must satisfy `0 < car < n//2`.

**Returns**

Real non-negative `n × n` intensity array:

```python
abs(sensor_field + exp(2j*pi*car*x/n))**2
```

**Raises**

`ValueError` if the field is not square 2-D or if the carrier is outside the allowed range.

**Physical note**

The ideal model has unit reference amplitude and no camera response, shot noise, read noise, dark offset, flat-field structure, saturation, or quantization.

### `reconstruct_field(hologram, car=CAR_DEFAULT, win=WIN_DEFAULT)`

Extract the negative-x sideband and shift it to baseband.

**Parameters**

- `hologram`: square 2-D real-valued finite array.
- `car`: integer carrier in Fourier bins.
- `win`: integer non-negative sideband half-width in bins, less than `n//2`.

The selected crop is centered at Fourier coordinates approximately `(n//2, n//2-car)` and spans `2*win+1` bins per axis before zero-filled repositioning.

**Returns**

Square complex reconstructed field at the sensor sampling grid.

**Raises**

`ValueError` for non-square input, non-finite values, non-integer carrier/window, invalid ranges, or a crop that cannot fit in the centered Fourier spectrum.

**Physical note**

The crop is a hard rectangular filter. A crop-fit check is not evidence that the measured sideband is optically separated from DC and the conjugate sideband; the caller must verify separation from measured spectral support.

### `offaxis_field(sensor_field, car=CAR_DEFAULT, win=WIN_DEFAULT)`

Convenience composition of `record_hologram(sensor_field, car)` followed by `reconstruct_field(hologram, car, win)`.

Returns the reconstructed complex baseband field. It is equivalent to:

```python
hologram = record_hologram(sensor_field, car)
baseband = reconstruct_field(hologram, car, win)
```

## `waveholo_telescope.metrics`

### `aperture_contrast(field, mask)`

Calculate the pupil-support intensity contrast used as the primary focus metric.

**Parameters**

- `field`: complex field array.
- `mask`: Boolean array with the same shape, containing both inside and outside pixels.

**Returns**

Finite float in the nominal range `[-1, 1]`:

```python
(mean_inside - mean_outside) / (mean_inside + mean_outside)
```

Returns `0.0` when the denominator is non-positive or non-finite. Raises `ValueError` for incompatible shapes or an all-inside/all-outside mask.

### `eroded_mask(rho, radius, erode)`

Return a circular mask eroded inward by a pixel distance.

**Parameters**

- `rho`: normalized radial coordinate array.
- `radius`: positive pupil radius in pixels.
- `erode`: non-negative erosion in pixels.

**Returns**

Boolean array equivalent to `rho <= 1 - erode/radius`. With `erode=0`, this equals the ordinary circular mask. Raises `ValueError` for invalid radius or negative/non-finite erosion.

### `phase_rms_error(field, true_phase_waves, mask)`

Calculate wrapped recovered-minus-true phase RMS in waves after circular piston removal.

The recovered phase and true phase each have their circular mean piston removed. The residual is wrapped to `[-0.5, 0.5)` waves, then its ordinary RMS is returned.

**Parameters**

- `field`: complex reconstructed field.
- `true_phase_waves`: reference phase in waves, same shape.
- `mask`: Boolean comparison support, same shape and non-empty.

**Returns**

Float RMS error in waves.

### `phase_agreement(field, true_phase_waves, mask)`

Calculate circular phase agreement:

```python
abs(mean(exp(2j*pi*wrapped_residual_waves)))
```

Returns a float from `0` to `1`, where `1` means perfect circular agreement. The same piston removal and wrapped residual convention as `phase_rms_error` is used.

### `phase_variance(field)`

Calculate the intensity-weighted circular phase variance:

```python
1 - abs(sum(abs(field)**2 * exp(1j*angle(field))) / sum(abs(field)**2))
```

Returns `0` for a perfectly uniform phase and approaches `1` for circularly dispersed phase. Returns `1.0` for zero or non-finite total intensity. This is a secondary diagnostic and is not a reliable focus metric for the aberrated telescope pupil demonstrated by this project.

## `waveholo_telescope.analysis`

### `focus_sweep(base_field, pupil_mask, distances, *, dx=None, wl=None)`

Evaluate aperture contrast over candidate back-propagation distances.

**Parameters**

- `base_field`: reconstructed complex sensor-plane field.
- `pupil_mask`: Boolean expected pupil support with matching shape.
- `distances`: non-empty 1-D iterable of finite, non-negative, strictly increasing distances in metres.
- `dx`: optional propagation pitch in metres. If omitted, `DX` is used.
- `wl`: optional wavelength in metres. If omitted, `WL` is used.

**Returns**

`(distances_array, contrasts_array)` with float dtype and the same input order. Each score is calculated from `angular_spectrum(base_field, -distance, ...)` and `aperture_contrast`.

**Raises**

`ValueError` for invalid distances or shape mismatch.

**Example**

```python
import numpy as np
from waveholo_telescope import focus_sweep

distances = np.arange(0, 10.0001e-3, 0.25e-3)
d, scores = focus_sweep(baseband, mask, distances)
```

### `parabolic_peak(distances, scores)`

Refine the sampled maximum of a focus score curve using a local three-point parabola.

**Parameters**

- `distances`: matching finite 1-D distance array.
- `scores`: matching finite 1-D score array.

**Returns**

A dictionary containing:

| Key | Meaning |
|---|---|
| `sampled_distance_m` | Distance at the sampled maximum |
| `refined_distance_m` | Quadratic refinement when the maximum is interior and the local parabola is concave; otherwise sampled distance |
| `score` | Score at the sampled maximum |
| `curvature_per_m2` | Fitted local curvature, or JSON-safe `null` when unavailable |
| `resolution_half_step_m` | Half the smallest adjacent distance step, or `null` for one sample |
| `at_boundary` | Whether the sampled maximum is the first or last point |
| `plateau` | Whether multiple samples share the maximum within numerical tolerance |
| `weak_curvature` | Whether local curvature is too weak to support stable interpolation |
| `refinement_applied` | Whether an interior concave fit had a vertex within adjacent samples |

Distances may be irregular but must be strictly increasing and nonduplicate. Refinement is a local quadratic interpolation, not a confidence interval. A boundary maximum should trigger a wider or better-centered sweep before interpretation.

## Statistical utility conventions

`paired_bootstrap_difference` reports the first column minus the second column for each pair before resampling. `power_analysis_proportion` estimates equal per-group sample size for an independent two-group proportion comparison using a two-sided normal approximation and pooled null variance. For example, `power_analysis_proportion(0.05, 0.15, alpha=0.05, power=0.8)` returns 141 observations per group. These are planning approximations, not measured performance.

The claim gate reports `pass`, `fail`, or `insufficient_evidence`; scientific acceptance remains insufficient until supported by a frozen protocol. The smoke profile checks explicitly configured synthetic engineering thresholds only, and `physical_claim` remains false.

## Top-level exports

The following names are re-exported by `waveholo_telescope`:

```python
from waveholo_telescope import (
    angular_spectrum,
    pupil_field,
    pupil_grid,
    zernike_phase,
    record_hologram,
    reconstruct_field,
    offaxis_field,
    focus_sweep,
    parabolic_peak,
    aperture_contrast,
    eroded_mask,
    phase_rms_error,
    phase_agreement,
    phase_variance,
    N,
    DX,
    WL,
    CAR_DEFAULT,
    WIN_DEFAULT,
)
```

## Reproducibility and testing

Run the package's regression suite from the repository root:

```sh
python -m unittest discover -s tests -v
```

Run the synthetic benchmark:

```sh
python demo.py
waveholo-benchmark --config smoke --output results/smoke
```

The test suite is based on Python's standard `unittest` and NumPy; it does not require SciPy. Test thresholds are regression guards, not universal physical acceptance thresholds. `worldholo-benchmark` is retained as a compatibility alias.

## Compatibility and limitations

The public API currently assumes square arrays, scalar monochromatic propagation, integer horizontal carrier bins, and a circular pupil model. It does not provide camera calibration, arbitrary-angle/fractional carrier estimation, phase unwrapping, atmospheric modeling, non-circular pupil registration, or statistical uncertainty estimation. See [`TECHNICAL_DOCUMENTATION.md`](TECHNICAL_DOCUMENTATION.md) and [`PHYSICAL_READINESS.md`](../PHYSICAL_READINESS.md) before applying the code to recorded data.
