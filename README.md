# WaveHolo Telescope

Synthetic off-axis digital-holography benchmark for focus and wavefront recovery
from a telescope pupil under parameterized Zernike aberrations.

**Evidence status:** SYNTHETIC only. No real telescope data.

**What this is:** A reproducible pre-implementation benchmark for evaluating
focus and wavefront-recovery methods under controlled aberrations and noise.

**What this is not:** A validated telescope, adaptive-optics system, atmospheric-turbulence
model validation, or demonstration on real observational data.

## What this repository does

It simulates a circular pupil, injects a documented subset of Zernike phase terms,
propagates and records an off-axis hologram, reconstructs the pupil field, estimates
focus, and reports phase residuals against simulation ground truth.

## What this repository does not do

It does not process or validate real telescope observations, model validated
atmospheric turbulence, control adaptive optics, or establish astronomical,
observatory, or operational performance.

## Scientific question

Under synthetic telescope-pupil conditions with parameterized Zernike aberrations
and noise, what is the accuracy and robustness of focus and wavefront recovery?

## Method overview

The current basis consists of unnormalized defocus, astigmatism, and coma terms;
coefficients are in waves and piston is removed for comparison. Aperture contrast
is maximized for focus. See [the scientific protocol](docs/SCIENTIFIC_PROTOCOL.md)
and [API reference](docs/API_REFERENCE.md).

## Primary metrics

Residual RMS wavefront error is primary. Focus error, coefficient error, and
sampling diagnostics are secondary. RMS phase error currently uses waves; radians
and OPD conversions require the declared simulation wavelength. Definitions are in
[METRICS.md](docs/METRICS.md).

## Reproducible quickstart

```bash
python -m pip install -e ".[test]"
make benchmark CONFIG=benchmarks/configs/telescope_smoke.yaml
```

The smoke benchmark is an engineering check, not a publication-level factorial
study. Results are written to a new directory and include provenance metadata. The
3-seed smoke run is expected to fail the 20-seed claim gate and return exit code 2;
that is a recorded gate failure, not a benchmark execution failure.

## Benchmark results summary

**UNRUN:** the preregistered factorial benchmark has not been run. No result is
estimated or projected. The nominal configuration is a design specification only;
the current runner cannot execute it until the radial-order basis, photon/read-noise
models, and factorial runner are implemented. The runnable smoke command is
`make benchmark CONFIG=benchmarks/configs/telescope_smoke.yaml OUTPUT=/tmp/telescope-smoke`.

The existing v0.2.0 demo reported 5.138 mm estimated versus 5.000 mm truth,
0.0066 waves RMS at estimated focus, and a negative result for phase-variance focus
selection. Those are historical deterministic synthetic demo values, not repeated
uncertainty-qualified benchmark results.

## Limitations and failure modes

The model uses an ideal circular pupil and a limited modal basis, with a rectangular
sideband filter and simplified noise. Higher-order mode recovery, photon/read-noise
effects, and the failure envelope are not yet established by the required factorial
study. See [LIMITATIONS.md](docs/LIMITATIONS.md).

## Real-data status

UNRUN. No real telescope data, atmospheric validation, laboratory instrument
measurements, or adaptive-optics loop results are included.

## Installation

Python 3.10+ and NumPy are required. Development and test dependencies can be
installed with `python -m pip install -e ".[test]"`.

## Testing

Run `make test` for unit, property, regression, and integration checks. CI runs a
small smoke benchmark; it does not run the full factorial matrix.

## Citation

Cite the version identified in [`CITATION.cff`](CITATION.cff).

## Licence and provenance

AGPL-3.0-only. Results are SYNTHETIC and refer to generated inputs and the exact code
commit recorded in each result manifest.
