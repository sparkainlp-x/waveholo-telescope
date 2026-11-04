# Reproducibility

## Focused repair audit (2026-11-04)

Purpose: repair synthetic measurement, acceptance, statistics and artifact
validation without claiming scientific readiness. Current main was verified
read-only as `cc75ed072c0a9e6ccd99338c3623b856c1041e6d`.
No branch was merged, release published, repository setting changed or other
PR modified.

Environment: Linux x86_64, Python 3.12.3, NumPy 2.5.4 in an isolated venv.
No physical telescope, quantum hardware, advantage or deployment claim follows.

## Exact local commands

These commands were run from the task checkout. Parent smoke outputs use
`/tmp`; worker build/install evidence uses the ignored `.venv/artifact-validation`
directory. No generated artifacts are committed. Fresh output paths are required.

```sh
ROOT=/home/runner/work/waveholo-telescope/waveholo-telescope
python -m venv /tmp/waveholo-repair-venv
/tmp/waveholo-repair-venv/bin/python -m pip install -e "$ROOT"
cd "$ROOT"
/tmp/waveholo-repair-venv/bin/python -m unittest discover -s "$ROOT/tests" -v
/tmp/waveholo-repair-venv/bin/python -m unittest discover -s "$ROOT/tests" -p test_benchmark.py -v
```

Initial discovery failed because NumPy was not installed. After installing
the declared dependencies, all **23 original tests passed**. Discovery's
default `test*.py` includes both `test_*.py` and the original `tests.py`;
the bug was insufficient coverage, not an excluded original test module.
The **12 focused measurement/configuration tests passed** after repair.

Final integrated discovery by the claims/statistics worker passed **58 tests**
(including 23 statistical/claim tests, the original optical tests and artifact
validator regressions). The existing demo also completed successfully:

```sh
TMPDIR="$ROOT/.claims-test-work" PYTHONPATH="$ROOT/src" \
  /tmp/waveholo-repair-venv/bin/python -m unittest discover -s "$ROOT/tests" -v
PYTHONPATH="$ROOT/src" /tmp/waveholo-repair-venv/bin/python "$ROOT/demo.py"
git -C "$ROOT" diff --check
```

The worker's scratch directory was created before discovery and removed after
the run; it is not part of this PR. No new test framework was introduced.

### Exact distribution validation

The artifact worker reproduced the baseline failure by building/installing the
original wheel into a fresh environment and invoking the legacy CLI with
`--config configs/v0.2.0-smoke.json` and `--config smoke` from `/`.
Both exited 1 with `FileNotFoundError`. The repair's packaged presets resolve
without checkout-relative files.

Final build tools: build 1.6.1 and Twine 7.0.0. Commands:

```sh
WORK="$ROOT/.venv/artifact-validation"
"$WORK/tools/bin/python" -m build --sdist --wheel --outdir "$WORK/final-contract"
"$WORK/tools/bin/python" -m twine check "$WORK/final-contract/"*
"$WORK/tools/bin/python" "$ROOT/tests/test_artifacts.py" \
  --dist "$WORK/final-contract" --work-dir "$WORK/final-contract-installs"
```

Both distributions passed Twine checks. The checker rebuilt the exact sdist,
installed each wheel into a separate fresh venv, and invoked both
`waveholo-benchmark` and `worldholo-benchmark` with `--config smoke` from `/`
(outside the checkout, without PYTHONPATH/PYTHONHOME). All four runs passed
strict JSON, checksum, nonempty installed-provenance and scope validation.
Raw results, analysis, claims and report were byte-identical across aliases
and distribution installs. Nine artifact validator regression tests passed.
Artifact integrity succeeded while smoke acceptance and scientific verdict
both remained **fail**.

Earlier reviewed snapshot identities, retained for audit (not a
reproducible-wheel-build claim):

| Artifact | SHA256 |
|---|---|
| Wheel | `539381a0ca19c9d03ca3f9549b3a4b7fea4be25df6d30a2a1299ccbb7fa74c4e` |
| Sdist | `d02c45c380c2dc47886e0b2c339ceebe7fc61bf1a1530b9ab3095e6399aa3417` |
| Wheel rebuilt from that sdist | `9b7c3c147031675aaf58d20d894d52a521d2b168efa4db4ebeadd71ba8a86b7b` |

Installed-wheel smoke provenance: seeds `[11,22,33]`, package 0.2.0,
UTC `2026-11-04T23:21:01.087182+00:00`, config SHA256
`00c60ad2717a3dd7bf8af63863dde85ea8cc27ae8d6048beb0c2a3680d6dcd22`,
package-content SHA256
`7a4a401bc13f2efb0161de9972f262f154b1b61e30795a2ebf6b744d274dadf7`.
That snapshot predates the final optional proportion-interval validation.

The final-contract run also passed all four installed smoke checks, provenance
and deterministic comparisons after rejecting invalid lower/upper/level fields
and inconsistent distribution counts. Its identities are:

| Artifact | SHA256 |
|---|---|
| Wheel | `8f463e85978e49e40375e18a2eff100f8af8c9431b3113cada5e480aae9a340f` |
| Sdist | `83ee7c4647f5b79d8d3bb10a1f9d1beac0aab45ae396723fa70136f2f3f40710` |
| Rebuilt wheel | `786bd55a2273246703a853bdac849a177e4d370c9c927468fee391e1d633183f` |

Final installed-wheel smoke: same seeds/version/config hash, UTC
`2026-11-04T23:23:28.561667+00:00`, package-content SHA256
`835464bff8e17aca6dcb4cad420389824e69418f8088b75fc97d9fbfca7f2756`.
Both verdicts remain **fail**. Subsequent documentation-only edits do not
change that tested package inventory. Generated evidence is ignored, not published.

The newly introduced checkout/setup-python Action references were verified
against GitHub commits and pinned to full SHAs. Advisory checks reported no
vulnerabilities for those references and the build/Twine tooling.

Baseline benchmark reproduction loaded the original module/config from Git
without changing branches:

```sh
/tmp/waveholo-repair-venv/bin/python - <<'PY'
import json, subprocess, types
from pathlib import Path
baseline = types.ModuleType("waveholo_telescope._baseline_benchmark")
baseline.__file__ = str(Path("src/waveholo_telescope/benchmark.py").resolve())
exec(subprocess.check_output(
    ["git", "show", "cc75ed0:src/waveholo_telescope/benchmark.py"], text=True),
    baseline.__dict__)
config = json.loads(subprocess.check_output(
    ["git", "show", "cc75ed0:configs/v0.2.0-smoke.json"], text=True))
print(baseline.run_benchmark(config)[1]["primary"])
PY
```

This uses the original benchmark code and configuration with the installed
statistical helpers; the reported RMS is computed before those helpers.
Repaired smoke command:

```sh
/tmp/waveholo-repair-venv/bin/python - <<'PY'
from waveholo_telescope.benchmark import main
main(["--config", "smoke", "--output", "/tmp/waveholo-repair-smoke"])
PY
```

## Reproduced findings and repaired outcomes

| Finding | Original | Repaired |
|---|---|---|
| Measurement path | Baseband computed then ignored; recorded intensity propagated | Baseband consumed by focus and all wavefront diagnostics; intensity retained only as an explicitly incorrect control |
| Smoke median measured-focus RMS | 0.234329338316051 waves | 0.011407298134095772 waves |
| Smoke threshold / successes | 0.01 waves / 0 of 3 | Unchanged: 0.01 waves / 0 of 3; smoke gate **fail** |
| Missing focus curvature | JSON `NaN` at boundary | JSON `null`; strict serialization rejects non-finite numbers |
| Negative RMS claim | `-1.0` could pass | Invalid metrics fail closed |
| Threshold forwarding | Analysis used config; gate used defaults | Shared resolved acceptance in analysis, gate, manifest and report |
| Primary condition | Last noise list element | Required explicit `primary_noise_sigma`; ordering has no decision meaning |
| Focus interpretation | Search centered on true distance | Local search uses a supplied coarse prior; blind mode takes a fixed independent range |
| Scientific wording | Smoke described as preregistered | No verified frozen protocol; smoke is not scientific evidence |
| Phase-variance control | Hard-coded measured verdict | Clearly labeled prior finding, not retested; intensity ablation is computed |

The low-grid API default also changed from the old ad-hoc 64:(16,15)
sampling to the reviewed 64:(20,12) preset. At that same repaired sampling,
the deliberate intensity-path ablation gives 0.20919102019757024 waves
measured-focus RMS versus 0.04595275674637843 for baseband (seed 11,
64 grid, radius 16, sigma 0.05, three sweep points). Both reach a search
boundary: this is **not** evidence of successful blind acquisition.
Both supplied presets set the coarse prior **equal to simulated truth**;
the manifest/report disclose this explicitly. Their local smoke runs do not
provide independent acquisition evidence, and no search range was retuned.
The integration test patches the reconstruction return field and checks
its identity at the measurement calls; independent plane-wave and known
pupil checks guard numerical correctness.

Statistical reference checks preserve original input order for shuffled
Benjamini–Hochberg inputs (e.g. `[.2,.001,.041,.008,.039]` maps to
`[.2,.005,.05125,.02,.05125]`), check Wilson's canonical 5/10 interval
`[0.236593090512564, 0.763406909487436]`, and exercise bootstrap shape/type,
count, alpha and seed validation. BH's algorithm was already correct; its
original monotonicity test was tautological.

The original proportion-power utility returned **79** for p0=.05, p1=.15,
alpha=.05 and power=.8. The corrected design returns **141 per group**:

`ceil((z_(1-alpha/2)*sqrt(2*pbar*(1-pbar)) +
z_power*sqrt(p0*(1-p0)+p1*(1-p1)))^2 / (p1-p0)^2)`,
where `pbar=(p0+p1)/2`.

This is the uncorrected normal approximation for two-sided, equal-allocation,
independent iid Bernoulli groups, not a paired or one-sample design. Reference
tests use standard-library normal quantiles and fixed numerical cases
(also 199 per group for .1 versus .2). It is a design approximation, not an
exact guarantee; no scientific benchmark was launched to validate power.

All numerical outcomes above are **SYNTHETIC**, not instrument measurements.
The reported phase RMS is wrapped, piston-removed and evaluated on an eroded
known pupil; it is not unwrapped wavefront or generalization evidence.

## Acceptance, compatibility and provenance

Artifact/config schema **2.0** replaces 1.0 for this unreleased repair.
Package metadata remains 0.2.0; source-content and distribution hashes, not
that version alone, identify this repair. Earlier outputs and historical
demo bars are retained, but raw-intensity benchmark interpretations and
unsupported preregistration/positive scientific interpretations are invalidated.
No old result files were regenerated in place.

`primary_rms_threshold` and `min_success_fraction` are validated once by the
shared resolver. Nested `acceptance` is also accepted; conflicting duplicate
thresholds are rejected. Seeds must be unique nonnegative integers; counts
must be genuine integers. Noise conditions must be finite, nonnegative,
unique, and contain the explicitly declared primary condition. Booleans,
numeric strings and non-finite metric/configuration values are not numbers
for these contracts. Duplicate JSON object keys are rejected.

Packaged presets mirror the explicit JSON configs with an equality regression
test. Compatible sampling presets preserve 256:(80,48), 128:(40,24) and
64:(20,12). Fourier-array fit is **not** proof of optical sideband separation.

Each output bundle records seeds/config, UTC generation time, actual package
metadata version, installed package source/config hashes, content identity,
installed RECORD hash when available, environment and config hashes, and
checksums for every result file. Checkout commit and dirty status are recorded
when available; missing required source inventory fails. These hashes identify
content, not a signature, protocol freeze or attestation. JSON is strict.

## PR overlap and attribution (read-only inspection)

All three current diffs, heads and review threads were inspected; review
threads were empty at inspection. No branches were combined.

- **#2**, `41ea880996449c1d5b4ba2f95633483206239573`
  (Copilot): overlaps noise placement, compatible sampling, shared acceptance,
  strict JSON, installed-module hashing, statistical corrections and packaged
  CLI presets. Those repair patterns informed this implementation and were
  tested locally, not treated as inherited evidence. Its richer phase-variance
  sweep is not imported: this repair explicitly labels that result as prior.
- **#3**, `38217f0a20e6a8cf038a05a3c2651da4a747a94d`
  (@sparkainlp-x): informs the separation between engineering smoke and
  scientific evidence. Its factorial protocol, OSA/ANSI expansion, YAML/Make
  infrastructure and 20-seed exit-2 gate are not imported. They are different
  designs; their presence does not verify a frozen protocol here.
- **#4**, `964da9afa36b45d51be297b9e79b1bc0df1c928d`
  (@sparkainlp-x): the baseband routing, sampling validation/presets and
  reconstruction-consumption regression are adapted with attribution.
  Scope overlaps the same benchmark/hologram/test hunks; future integration
  requires reconciliation, not duplicate application. Its unrelated
  concurrency-policy change is not imported.

Conflicts resolved explicitly: CLI exit 0 means completed artifact generation,
not scientific acceptance; `claim_gate_status` describes smoke acceptance and
`scientific_verdict` is separate. Neither PR #3's seed-gate semantics nor
PR #2's different verdict vocabulary is silently substituted.

GitHub Actions runs were inspected via the API, including #4's
`41770303749` (all six jobs successful) and smoke job `126378321724` logs.
That prior green run is REPORTED technical evidence for #4, not a scientific
result or a CI result for this repair.

## Evidence status
- Repaired bounded smoke: SYNTHETIC; negative acceptance outcome preserved.
- Original demo bars: REPORTED historical results, not current acceptance.
- Frozen protocol verification, empty-pupil control, independent blind-
  acquisition study, sideband-width sensitivity and full radial-order 2–10
  factorial: UNRUN.
- Physical/hardware/paid/full-scale evaluations: UNRUN; not started.
- Python 3.10/3.11/3.13 execution and hosted CI for this repair: UNRUN locally.
- No benchmark threshold was retuned to force a pass.

## Claim gates
Smoke acceptance is not a seed gate or scientific verdict. A failed gate is
an honest negative result, not a reason to block artifact integrity validation
or to relax success criteria. Missing protocol/control evidence never supports
a positive scientific claim. No protocol is called preregistered here.

## Security review

Changed files passed secret scanning. The first CodeQL review found no Python
alerts and one missing-token-permissions alert in the new clean-install job;
that job now explicitly grants only `contents: read`. The final review result
is recorded with the PR checks; no scientific verdict follows from security
validation.
