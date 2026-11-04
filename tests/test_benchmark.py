# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from waveholo_telescope.analysis import focus_sweep
from waveholo_telescope.benchmark import main, run_condition
from waveholo_telescope.hologram import record_hologram, reconstruct_field
from waveholo_telescope.propagation import DX, WL, angular_spectrum
from waveholo_telescope.pupil import pupil_field


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
            self.assertIn(claims["claim_gate_status"], {"pass", "fail", "inconclusive"})
            forbidden = (
                "telescope-ready",
                "works on telescopes",
                "validates physical holography",
                "ready for observatory deployment",
            )
            claims_text = json.dumps(claims).lower()
            self.assertFalse(any(phrase in claims_text for phrase in forbidden))

            for line in (output / "checksums.sha256").read_text().splitlines():
                expected, filename = line.split("  ", 1)
                actual = hashlib.sha256((output / filename).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, filename)

    def test_repeated_benchmarks_have_deterministic_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "run-a"
            second = Path(directory) / "run-b"
            self.assertEqual(main(["--config", "configs/v0.2.0-smoke.json", "--output", str(first)]), 0)
            self.assertEqual(main(["--config", "configs/v0.2.0-smoke.json", "--output", str(second)]), 0)
            for name in ("analysis.json", "claims.json", "report.md"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)

    def test_invalid_carrier_and_window_are_rejected_before_fft(self):
        invalid_settings = (
            {"carrier": 0, "window": 12},
            {"carrier": 32, "window": 0},
            {"carrier": 20, "window": 32},
            {"carrier": 21, "window": 12},
            {"carrier": 20.5, "window": 11},
        )
        for settings in invalid_settings:
            with self.subTest(**settings), patch("numpy.fft.fft2") as fft2:
                with self.assertRaises(ValueError):
                    run_condition(seed=11, n=64, radius=16, sweep_points=3, **settings)
                fft2.assert_not_called()

    def test_valid_grid_boundary_reconstructs_before_focus_sweep(self):
        pupil, _, _ = pupil_field(
            64, 16, defocus=0.4, astig_x=0.3, coma_x=0.2
        )
        sensor = angular_spectrum(pupil, 5e-3, dx=DX, wl=WL)
        expected = reconstruct_field(record_hologram(sensor, 20), 20, 12)

        with patch("waveholo_telescope.benchmark.focus_sweep", wraps=focus_sweep) as sweep:
            run_condition(
                seed=11, n=64, radius=16, carrier=20, window=12,
                noise_sigma=0, sweep_points=3,
            )

        actual = sweep.call_args.args[0]
        self.assertTrue((actual == expected).all())


if __name__ == "__main__":
    unittest.main()
