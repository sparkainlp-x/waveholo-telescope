# Reproducibility Manifest

This document defines how to reproduce the WaveHolo Telescope synthetic benchmark and how to preserve release provenance.

## Environment

Record the following before running a validation benchmark:

- Operating system and version.
- Python version.
- NumPy and direct dependency versions.
- CPU architecture or accelerator, if relevant.
- Repository commit SHA.
- Random seed, where applicable.

## Standard commands

From a clean clone:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m unittest discover -s tests -v
python demo.py
waveholo-benchmark --config smoke --output results/smoke
```

`worldholo-benchmark` remains a compatibility alias. The packaged `smoke`
and `primary` presets are available from installed wheels. CI also builds
and installs a wheel in an isolated environment, runs outside the checkout,
and invokes the installed CLI.

## Benchmark parameters

The documented 256 by 256 synthetic benchmark uses:

- Wavelength: 532 nm.
- Pixel pitch: 6.5 micrometers.
- Carrier frequency: 80 bins.
- Sideband half-width: 48 bins.
- Pupil-to-sensor distance: 5.00 mm.
- Documented lower-resolution numerical presets: `128:(40, 24)` and
  `64:(20, 12)`, preserving the same pitch, wavelength, and distance.
- Unknown grid sizes require explicit carrier and window settings. Fourier
  crop fit is not a physical sideband-separation test.

## Acceptance profiles

The smoke profile is an engineering check against configured synthetic
thresholds, not scientific acceptance. The scientific profile reports
insufficient evidence until a genuinely frozen protocol and supporting
evidence exist. These criteria are not described as preregistered, and
`physical_claim` remains false regardless of synthetic results.

## Required release artifacts

For each tagged release, retain:

- Source archive.
- Built wheel, when applicable.
- Test-log summary.
- Benchmark metrics in machine-readable form.
- Generated figures, where applicable.
- Exact commit SHA and tag name.
- Corrected `raw_results.json`, analysis, claims, report, and checksums from a
  fresh run; do not reuse pre-correction benchmark outputs.

## Change control

After a release tag is published:

- Do not move, delete, or rewrite the tag.
- Do not replace release assets.
- Do not edit published release notes in ways that change scientific claims.
- Make corrections in a new release and describe the correction in the changelog.
