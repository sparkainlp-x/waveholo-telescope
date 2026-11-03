# Architecture

`src/waveholo_telescope/` separates pupil generation, propagation, hologram
formation/reconstruction, focus analysis, metrics, experiment orchestration,
statistics, and claim gating. The benchmark entry point is
`waveholo_telescope.benchmark`; its current JSON config and result layout predate
the requested complete factorial schema.

`benchmarks/configs/` defines immutable experiment inputs. `benchmarks/results/`
contains only schemas/templates and small fixtures. A run writes per-seed records,
summaries, environment and provenance, checksum inventory, and regenerated figures
to a caller-selected output directory. Claims are downstream of checksum and
completeness validation; claims cannot alter measured values.
