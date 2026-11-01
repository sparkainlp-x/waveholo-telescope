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
python -m pip install -e .
pytest
python demo.py
```

If the project later adds a dedicated benchmark entry point, replace `python demo.py` with that command and retain the original command as a compatibility fallback.

## Benchmark parameters

The documented 256 by 256 synthetic benchmark uses:

- Wavelength: 532 nm.
- Pixel pitch: 6.5 micrometers.
- Carrier frequency: 80 bins.
- Sideband half-width: 48 bins.
- Pupil-to-sensor distance: 5.00 mm.

## Required release artifacts

For each tagged release, retain:

- Source archive.
- Built wheel, when applicable.
- Test-log summary.
- Benchmark metrics in machine-readable form.
- Generated figures, where applicable.
- Exact commit SHA and tag name.

## Change control

After a release tag is published:

- Do not move, delete, or rewrite the tag.
- Do not replace release assets.
- Do not edit published release notes in ways that change scientific claims.
- Make corrections in a new release and describe the correction in the changelog.
