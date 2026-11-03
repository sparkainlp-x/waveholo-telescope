# Implementation plan

The changes are intended as small, independently reviewable pull requests. The
current patch is a first foundation slice, not completion of every stage.

1. `docs: add scientific protocol and claims policy` — protocol, metrics,
   limitations, real-data status, validation matrix, and claim gates.
2. `feat(metrics): add reconstruction and focus metrics` — formulas, units,
   coefficient-domain metrics, and tested focus selection.
3. `feat(simulation): add deterministic synthetic benchmark fixtures` — fixed
   pupil and aberration fixtures with normalization tests.
4. `feat(experiments): add factorial benchmark runner` — radial-order, amplitude,
   sampling, and photon/read-noise design.
5. `test: add unit, property, regression, and integration tests` — orthonormality,
   serialization, schemas, seeds, and claim gates.
6. `feat(reporting): add manifests, checksums, figures, and claim gates` — complete
   output schema, uncertainty tables, and generated figure set.
7. `docs: add limitations, validation matrix, and reproducibility guide` — verify
   commands and actual runner semantics.
8. `benchmark: run smoke benchmark and archive results` — record exact commit and
   retain both positive and negative outcomes.
9. `benchmark: run full protocol benchmark and publish summary` — execute only
   after basis/noise implementation satisfies the locked protocol.
10. `docs: update README with measured results and failure envelope` — update only
    from a complete, validated run.
