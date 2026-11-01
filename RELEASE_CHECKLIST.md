# Release Checklist

Use this checklist before publishing any tagged release.

## Code and tests

- [ ] All automated tests pass from a clean checkout.
- [ ] The documented demo or benchmark command runs successfully.
- [ ] No secrets, credentials, private keys, or local absolute paths are committed.
- [ ] License, copyright, and citation metadata are current.

## Scientific integrity

- [ ] Every quantitative claim is traceable to a reproducible command or test.
- [ ] Synthetic results are explicitly labeled as synthetic.
- [ ] Limitations are stated in the release notes.
- [ ] Null, aberration-free, noise, and ablation controls are documented or explicitly deferred with a reason.
- [ ] No claim exceeds the validated scope in `SCIENTIFIC_VALIDATION.md`.

## Reproducibility

- [ ] Python and dependency versions are recorded.
- [ ] Random seeds and deterministic settings are recorded.
- [ ] Benchmark dimensions, wavelength, pixel pitch, carrier frequency, sideband width, and propagation distance are recorded.
- [ ] The complete command sequence regenerates benchmark outputs.
- [ ] Release assets are retained unchanged after publication.

## Versioning

- [ ] Version number is updated in project metadata.
- [ ] `CHANGELOG.md` contains a dated entry for the release.
- [ ] The release tag points to the intended commit on the default branch.
- [ ] The release is marked Latest unless it is explicitly historical.

## Publication

- [ ] Release title uses the format: `WaveHolo Telescope vX.Y.Z`.
- [ ] Release notes include Added, Changed, Fixed, Validation, and Limitations sections where applicable.
- [ ] Source archive and any built wheel are attached or linked.
- [ ] The release URL is recorded in project outreach materials only after publication.
