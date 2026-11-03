# Scientific protocol

**Status:** protocol specification; requested factorial benchmark is UNRUN.
**Evidence label:** SYNTHETIC only.

## 1. Research question

**Primary question:** Under synthetic telescope-pupil conditions with parameterized
Zernike aberrations and noise, what is the accuracy and robustness of focus and
wavefront recovery?

**Secondary questions:**
- How does wavefront-recovery error vary with Zernike mode, amplitude, and order?
- How does focus-recovery error vary with photon noise, read noise, and pupil sampling?
- What is the failure threshold for each condition?
- Are observed differences stable across independent random seeds?

## 2. Hypotheses

- H1: Residual RMS wavefront error increases monotonically with injected Zernike
  aberration amplitude when the recovery method, mode basis, and sampling are fixed.
- H2: Focus-recovery error increases with photon noise and read noise.
- H3: Higher-order Zernike recovery requires sufficient pupil sampling;
  undersampling produces mode aliasing and increased reconstruction error.

Each hypothesis is tested only over the finite declared grid. A trend over that grid
does not imply behavior outside its tested conditions.

## 3. Experimental design

Independent factors: radial orders 2–10, amplitudes low/medium/high/extreme, photon
noise levels, read-noise levels, and pupil sampling undersampled/nominal/oversampled.
Exact values and parameter units must be explicit in config. Dependent outcomes:
residual RMS wavefront error; coefficient RMSE and per-mode error; focus error;
failure fraction; sampling error; robustness degradation; runtime and peak memory.

Control wavelength, pupil geometry, pupil mask, propagation and hologram algorithms,
reference wave, sideband filter, phase convention, and reconstruction sweep. Use
explicit independent seeds; at least 20 for each stochastic condition. If methods
are compared, use paired analysis only on identical seed, pupil, aberration, and
noise realizations. No learned component exists, so no data split is applicable;
if one is introduced, split by seed and aberration realization before tuning.

Exclude only invalid configurations or non-finite intermediate results specified
before execution. Keep and report all exclusions. Stop on completion or explicit
resource/configuration failure; incomplete outputs are PARTIAL or FAILED. Apply
Holm correction to confirmatory multi-mode tests and Benjamini-Hochberg to
exploratory families. Success/failure cutoffs are exact, fixed in the config, and
must not be tuned after results are seen.

## 4. Preregistration

See [`BENCHMARK_PROTOCOL.md`](BENCHMARK_PROTOCOL.md), protocol
`PROTOCOL-v1.0.0`. It was written before execution of the requested factorial
benchmark. Existing v0.2.0 smoke/demo numbers are historical and are not this
protocol's results.
