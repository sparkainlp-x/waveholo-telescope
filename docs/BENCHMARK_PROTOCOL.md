# Benchmark protocol

**Protocol version:** `PROTOCOL-v1.0.0`  
> This protocol is locked before benchmark execution.  
> Changes after execution require a new protocol version and must not overwrite prior results.

## Fixed conventions and inputs

The current implementation uses an explicitly documented low-order, unnormalized
circular-pupil basis in `src/waveholo_telescope/pupil.py`: defocus
`2ρ²−1`; astigmatism `ρ² cos(2θ)` / `ρ² sin(2θ)`; coma
`(3ρ³−2ρ) cos(θ)` / `sin(θ)`. Coefficients are in waves; phase is
`2πφ` radians. This is a project-specific basis subset, not a complete Noll,
Fringe, or OSA/ANSI ordering. The radial-order 2–10 experiment is blocked until
orthonormal basis terms, explicit mode IDs, and conversion/orthogonality tests are
implemented. Do not label the current five terms as the full requested basis.

## Factorial design and randomization

Use the checked-in nominal YAML design config once its factors are supported. Cross
OSA/ANSI mode IDs 3–65, four amplitudes, photon noise, read noise, and three
sampling levels. Use at least 20 seeds per stochastic cell; nominal config uses 20
minimum. Seed each independent random source explicitly
and store the full parameter map per row. Generate hologram noise with a Poisson
photon-count process followed by independent zero-mean Gaussian read noise. Define
gain, offset, clipping, and photon-to-count scaling in config. Current
`_add_sensor_noise` currently implements relative additive Gaussian noise and
non-negative clipping only; it is not a photon-count plus read-noise model, so
those factorial cells stay UNRUN until implemented.

The legacy basis-to-OSA/ANSI mapping is:

| Legacy term | OSA/ANSI `(n,m)` | OSA/ANSI `j` | Legacy polynomial vs normalized mode |
|---|---:|---:|---|
| defocus | (2, 0) | 4 | legacy = normalized / √3 |
| astig_x | (2, +2) | 5 | legacy = normalized / √6 |
| astig_y | (2, −2) | 3 | legacy = normalized / √6 |
| coma_x | (3, +1) | 8 | legacy = normalized / √8 |
| coma_y | (3, −1) | 7 | legacy = normalized / √8 |

This table documents polynomial scaling only; it is not an implemented conversion
API. Mode recovery remains blocked until the complete basis and mapping receive
orthogonality and coefficient-conversion tests.

## Analysis

Primary metric: pupil-domain residual RMS wavefront error, after predeclared piston
removal and mask selection. Also report coefficient RMSE/per-mode error, focus
error, and failure. Convert phase error to radians (`2π × waves`), waves at
simulation wavelength, and OPD nm (`waves × λ_nm`) when wavelength is defined.
Report Strehl only if its scalar phase assumptions are validated for the simulated
pupil; otherwise mark not applicable. Focus is aperture-contrast maximum; a
boundary maximum or flat curve below predeclared curvature/contrast threshold is a
failure.

For each cell report N, mean, median, standard deviation, 95% confidence interval,
minimum, maximum, and failure rate. Use 10,000-resample percentile bootstrap
intervals where distributional assumptions are unclear. Report effect size and
confidence interval. Paired tests require matched realizations. Apply Holm
correction to confirmatory comparisons across modes; Benjamini-Hochberg for
exploratory families. Statistical significance and practical threshold are reported
separately.

## Provenance and claim thresholds

No positive threshold is authorized until the radial basis, sensor noise model, and
explicit success thresholds are implemented and covered by tests. Current historical
smoke criteria are not silently promoted to these thresholds. Missing required
seed/metric, config mismatch, checksum failure, claim-gate failure, or absent commit
SHA makes the result invalid.

## Required output and figures

Machine-readable per-seed CSV/JSON precedes reports. Save manifest, config,
environment, commit, checksums, summary statistics, and code-generated figures:
pupil/aberrated phase; hologram; true/recovered coefficients; residual phase;
residual RMS versus amplitude; focus error versus noise; mode-by-sampling heatmap;
failure envelope. Captions state SYNTHETIC data, condition, metric, uncertainty,
units, and limitations. The requested full set is UNRUN until generated from a
complete protocol implementation.
