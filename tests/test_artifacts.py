# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
"""Validate exact distributions independently of scientific acceptance.

Run ``python tests/test_artifacts.py --dist dist --work-dir PATH`` after building.
Ordinary unittest discovery runs only the lightweight validator regression tests.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import venv


ARTIFACTS = {
    "manifest.json", "raw_results.json", "analysis.json", "claims.json", "report.md",
}
DETERMINISTIC_ARTIFACTS = ARTIFACTS - {"manifest.json"}


def canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def read_json(path):
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON constant: {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant,
                       object_pairs_hook=unique_object)
    json.dumps(value, allow_nan=False)
    return value


def validate_provenance(output, installed):
    manifest = read_json(output / "manifest.json")
    for key, value in installed.items():
        if manifest.get(key) != value:
            raise ValueError(f"Installed provenance mismatch: {key}")
    if manifest.get("source_inventory_status") != "complete":
        raise ValueError("Incomplete installed source inventory")
    for field, hashed_field in (("source_hashes", "package_content_sha256"),
                                ("environment", "environment_sha256")):
        if manifest.get(hashed_field) != canonical_hash(manifest[field]):
            raise ValueError(f"Invalid provenance hash: {hashed_field}")
    if manifest.get("config_sha256") != installed["source_hashes"]["configs/v0.2.0-smoke.json"]:
        raise ValueError("Smoke config does not match installed resource")
    if manifest.get("resolved_config_sha256") != canonical_hash({
        "config": manifest["config"], "acceptance": manifest["acceptance"],
    }):
        raise ValueError("Invalid resolved config hash")
    if "checkout_commit" in manifest or "checkout_dirty" in manifest:
        raise ValueError("Installed artifacts must not claim checkout provenance")


def validate_output(output):
    """Require complete, checksum-verified synthetic artifacts, not a passing claim."""
    expected = ARTIFACTS | {"checksums.sha256"}
    if {path.name for path in output.iterdir()} != expected:
        raise ValueError("Missing or unexpected benchmark artifacts")
    checksums = {}
    for line in (output / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        if name not in ARTIFACTS or name in checksums:
            raise ValueError("Invalid or duplicate checksum entry")
        checksums[name] = digest
    if set(checksums) != ARTIFACTS:
        raise ValueError("Incomplete checksum coverage")
    for name, digest in checksums.items():
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch: {name}")
    documents = {name: read_json(output / name) for name in ARTIFACTS if name.endswith(".json")}
    manifest = documents["manifest.json"]
    if not isinstance(manifest, dict) or not isinstance(documents["claims.json"], dict):
        raise ValueError("Manifest and claims must be JSON objects")
    sources = manifest.get("source_hashes")
    environment = manifest.get("environment")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Missing source provenance inventory")
    if any(not isinstance(digest, str) or len(digest) != 64
           or any(character not in "0123456789abcdef" for character in digest)
           for digest in sources.values()):
        raise ValueError("Invalid source provenance digest")
    if not isinstance(environment, dict) or not environment:
        raise ValueError("Missing environment provenance")
    for field, hashed_field in (("source_hashes", "package_content_sha256"),
                                ("environment", "environment_sha256")):
        if manifest.get(hashed_field) != canonical_hash(manifest[field]):
            raise ValueError(f"Invalid provenance hash: {hashed_field}")
    claims = documents["claims.json"]
    if claims.get("scope") != "synthetic_simulation_only":
        raise ValueError("Claim scope must remain synthetic_simulation_only")
    if claims.get("physical_claim") is not False:
        raise ValueError("Physical claims are not supported")
    if claims.get("claim_gate_status") not in {"pass", "fail", "inconclusive"}:
        raise ValueError("Invalid smoke acceptance status")
    if claims.get("scientific_verdict") not in {"fail", "inconclusive"}:
        raise ValueError("Artifact smoke cannot establish a positive scientific verdict")
    print("Artifact integrity passed; smoke acceptance:", claims["claim_gate_status"],
          "; scientific verdict:", claims["scientific_verdict"])


def validate_distributions(dist, work_dir):
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("Expected exactly one wheel and one sdist")
    work_dir.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    # Never resolve package imports or configuration relative to the checkout.
    outside_checkout = Path(work_dir.anchor)

    def run(*command, capture_output=False):
        return subprocess.run(command, cwd=outside_checkout, env=environment,
                              check=True, capture_output=capture_output, text=True)

    for artifact in (wheels[0], sdists[0]):
        print(f"SHA256 {hashlib.sha256(artifact.read_bytes()).hexdigest()}  {artifact.name}", flush=True)
    rebuilt = work_dir / "rebuilt"
    run(sys.executable, "-m", "pip", "wheel", "--no-deps",
        "--wheel-dir", str(rebuilt), str(sdists[0]))
    rebuilt_wheels = list(rebuilt.glob("*.whl"))
    if len(rebuilt_wheels) != 1:
        raise ValueError("Expected exactly one rebuilt sdist wheel")
    reference = None
    for label, wheel in (("wheel", wheels[0]), ("sdist", rebuilt_wheels[0])):
        install = work_dir / label
        venv.EnvBuilder(with_pip=True).create(install)
        python = install / "bin" / "python"
        run(str(python), "-m", "pip", "install", str(wheel))
        probe = run(str(python), "-I", "-c", """
import hashlib, json, platform, sys
from importlib import metadata
from pathlib import Path
import numpy
import waveholo_telescope
package = Path(waveholo_telescope.__file__).resolve().parent
assert package.is_relative_to(Path(sys.prefix).resolve()), "Import escaped clean environment"
hashes = {
    str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(package.rglob("*"))
    if path.is_file() and path.suffix in {".py", ".json"}
}
assert {"benchmark.py", "provenance.py", "configs/v0.2.0-smoke.json",
        "configs/v0.2.0-primary.json"} <= hashes.keys(), "Incomplete installed inventory"
distribution = metadata.distribution("waveholo-telescope")
record = distribution.read_text("RECORD")
assert record, "Missing installed RECORD"
print(json.dumps({
    "source_hashes": hashes,
    "package_version": distribution.version,
    "installed_record_sha256": hashlib.sha256(record.encode("utf-8")).hexdigest(),
    "environment": {"python_version": sys.version, "platform": platform.platform(),
                    "numpy_version": numpy.__version__},
}))
""", capture_output=True)
        installed = json.loads(probe.stdout)
        for command in ("waveholo-benchmark", "worldholo-benchmark"):
            output = work_dir / f"{label}-{command}"
            run(str(install / "bin" / command), "--config", "smoke", "--output", str(output))
            validate_output(output)
            validate_provenance(output, installed)
            deterministic = {name: (output / name).read_bytes() for name in DETERMINISTIC_ARTIFACTS}
            if reference is not None and deterministic != reference:
                raise ValueError("Nondeterministic outputs across aliases or distributions")
            reference = deterministic
    print("Installed provenance and deterministic outputs verified for both distributions and aliases.")


class TestArtifactValidation(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        for name in ARTIFACTS:
            (self.output / name).write_text("{}\n", encoding="utf-8")
        sources = {"benchmark.py": hashlib.sha256(b"fixture source").hexdigest()}
        environment = {"python_version": "fixture"}
        (self.output / "manifest.json").write_text(json.dumps({
            "source_hashes": sources,
            "package_content_sha256": canonical_hash(sources),
            "environment": environment,
            "environment_sha256": canonical_hash(environment),
        }), encoding="utf-8")
        self.write_claims()

    def write_claims(self, status="fail", scope="synthetic_simulation_only"):
        (self.output / "claims.json").write_text(json.dumps({
            "scope": scope, "physical_claim": False, "claim_gate_status": status,
            "scientific_verdict": "fail" if status == "fail" else "inconclusive",
        }), encoding="utf-8")
        self.write_checksums()

    def write_checksums(self):
        (self.output / "checksums.sha256").write_text("".join(
            f"{hashlib.sha256((self.output / name).read_bytes()).hexdigest()}  {name}\n"
            for name in sorted(ARTIFACTS)
        ), encoding="utf-8")

    def test_smoke_acceptance_statuses_are_valid_artifacts(self):
        for status in ("pass", "fail", "inconclusive"):
            with self.subTest(status=status):
                self.write_claims(status=status)
                validate_output(self.output)

    def test_rejects_corruption(self):
        (self.output / "report.md").write_text("corrupted", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            validate_output(self.output)

    def test_rejects_incomplete_checksum_coverage(self):
        (self.output / "checksums.sha256").write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Incomplete checksum"):
            validate_output(self.output)

    def test_rejects_missing_artifact(self):
        (self.output / "manifest.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing or unexpected"):
            validate_output(self.output)

    def test_rejects_invalid_claim_status_or_scope(self):
        for status, scope in (("unknown", "synthetic_simulation_only"), ("pass", "physical")):
            with self.subTest(status=status, scope=scope):
                self.write_claims(status=status, scope=scope)
                with self.assertRaises(ValueError):
                    validate_output(self.output)

    def test_rejects_nonfinite_json_in_every_json_artifact(self):
        for name in sorted(ARTIFACTS):
            if not name.endswith(".json"):
                continue
            with self.subTest(name=name):
                path = self.output / name
                original = path.read_text(encoding="utf-8")
                path.write_text('{"value": NaN}', encoding="utf-8")
                self.write_checksums()
                with self.assertRaisesRegex(ValueError, "Non-finite JSON"):
                    validate_output(self.output)
                path.write_text(original, encoding="utf-8")

    def test_rejects_duplicate_keys_and_overflowing_json_numbers(self):
        path = self.output / "raw_results.json"
        for content in ('{"value": 1, "value": 2}', '{"value": 1e1000}'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.write_checksums()
                with self.assertRaises(ValueError):
                    validate_output(self.output)

    def test_rejects_missing_or_invalid_provenance(self):
        path = self.output / "manifest.json"
        original = read_json(path)
        for field in ("source_hashes", "package_content_sha256", "environment",
                      "environment_sha256"):
            with self.subTest(field=field):
                changed = dict(original)
                changed[field] = {}
                path.write_text(json.dumps(changed), encoding="utf-8")
                self.write_checksums()
                with self.assertRaises(ValueError):
                    validate_output(self.output)

    def test_rejects_positive_scientific_verdict(self):
        path = self.output / "claims.json"
        claims = read_json(path)
        claims["scientific_verdict"] = "pass"
        path.write_text(json.dumps(claims), encoding="utf-8")
        self.write_checksums()
        with self.assertRaisesRegex(ValueError, "positive scientific verdict"):
            validate_output(self.output)


if __name__ == "__main__":
    if "--dist" in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--dist", type=Path, required=True)
        parser.add_argument("--work-dir", type=Path, required=True)
        args = parser.parse_args()
        validate_distributions(args.dist.resolve(), args.work_dir.resolve())
    else:
        unittest.main()
