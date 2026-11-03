# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from waveholo_telescope.benchmark import _add_sensor_noise, main, run_condition


class TestBenchmark(unittest.TestCase):
    def test_condition_is_deterministic(self):
        first = run_condition(seed=11, n=64, radius=16, carrier=20, window=12, sweep_points=5)
        second = run_condition(seed=11, n=64, radius=16, carrier=20, window=12, sweep_points=5)
        first.pop("runtime_seconds")
        second.pop("runtime_seconds")
        self.assertEqual(first, second)

    def test_sensor_noise_rejects_complex_field(self):
        with self.assertRaises(ValueError):
            _add_sensor_noise([[1.0 + 1.0j]], 0.1, np.random.default_rng(1))

    def test_smoke_benchmark_writes_complete_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results"
            status = main(["--config", "configs/v0.2.0-smoke.json", "--output", str(output)])
            self.assertEqual(status, 2)
            for name in (
                "manifest.json", "raw_results.json", "analysis.json", "claims.json",
                "report.md", "checksums.sha256", "environment.json", "code_commit.txt",
                "metrics.csv", "per_seed_results.csv", "summary.csv", "summary.json",
                "raw_checksums.sha256", "figures/phase_rms_vs_noise.svg",
            ):
                self.assertTrue((output / name).is_file(), name)
            claims = json.loads((output / "claims.json").read_text())
            self.assertEqual(claims["scope"], "synthetic_simulation_only")
            self.assertFalse(claims["physical_claim"])
            self.assertEqual(claims["claim_gate_status"], "fail")
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertTrue(manifest["code_commit_sha"])
            self.assertIn(manifest["status"], {"COMPLETE", "INVALID"})
            self.assertIn("metrics.csv", manifest["output_checksums"])


if __name__ == "__main__":
    unittest.main()
