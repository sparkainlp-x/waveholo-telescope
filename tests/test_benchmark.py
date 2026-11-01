# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
import json
import tempfile
import unittest
from pathlib import Path

from waveholo_telescope.benchmark import main, run_condition


class TestBenchmark(unittest.TestCase):
    def test_condition_is_deterministic(self):
        first = run_condition(seed=11, n=64, radius=16, sweep_points=5)
        second = run_condition(seed=11, n=64, radius=16, sweep_points=5)
        self.assertEqual(first, second)

    def test_smoke_benchmark_writes_complete_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results"
            status = main(["--config", "configs/v0.2.0-smoke.json", "--output", str(output)])
            self.assertEqual(status, 0)
            for name in ("manifest.json", "raw_results.json", "analysis.json", "claims.json", "report.md", "checksums.sha256"):
                self.assertTrue((output / name).exists(), name)
            claims = json.loads((output / "claims.json").read_text())
            self.assertEqual(claims["scope"], "synthetic_simulation_only")
            self.assertFalse(claims["physical_claim"])


if __name__ == "__main__":
    unittest.main()
