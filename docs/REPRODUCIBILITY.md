# Reproducibility

Use a clean checkout and record protocol, exact config, commit SHA, UTC time, Python
and dependency versions, platform/CPU, seeds, input/output checksums, runtime, and
status. Outputs must be deterministic in serialization and machine-readable before
narrative reports.

The current runnable smoke command is:

```bash
make benchmark CONFIG=benchmarks/configs/telescope_smoke.yaml OUTPUT=/tmp/telescope-smoke
```

The full nominal factorial command is **UNRUN and currently blocked** by the
unimplemented radial-order basis and photon/read-noise factors; do not treat the
design config as executable until those gates are closed.

Each result directory contains `config.yaml`, `manifest.json`, `environment.json`,
`code_commit.txt`, `metrics.csv`, `per_seed_results.csv`, `summary.json`,
`figures/`, and `checksums.sha256`. Status is COMPLETE, PARTIAL, FAILED, or INVALID.
Missing required seed/metric, checksum mismatch, config divergence, failed claim
gate, or unknown commit invalidates the run.

Do not commit large raw outputs. `benchmarks/results/` stores only schema/template
files and small deterministic fixtures; archive actual runs as CI artifacts or
external data releases with a checksum manifest. The complete factorial run is not
part of ordinary CI.
