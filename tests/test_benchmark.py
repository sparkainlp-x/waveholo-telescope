# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from waveholo_telescope.benchmark import (
    _add_sensor_noise, main, run_condition,
)
from waveholo_telescope.hologram import record_hologram, reconstruct_field
from waveholo_telescope.propagation import angular_spectrum
from waveholo_telescope.pupil import pupil_field


class TestBenchmark(unittest.TestCase):
    def test_condition_is_deterministic(self):
        first = run_condition(seed=11, n=64, radius=16, sweep_points=5)
        second = run_condition(seed=11, n=64, radius=16, sweep_points=5)
        self.assertEqual(first, second)
        self.assertEqual(first["carrier_bins"], 20)
        self.assertEqual(first["sideband_half_width_bins"], 12)
        self.assertEqual(len(first["phase_variance_sweep"]), 5)
        self.assertIn("at_boundary", first["phase_variance_minimum"])

    def test_sensor_noise_is_deterministic_and_preserves_zero_noise(self):
        intensity = np.arange(16, dtype=float).reshape(4, 4)
        first = _add_sensor_noise(intensity, 0.2, np.random.default_rng(5))
        second = _add_sensor_noise(intensity, 0.2, np.random.default_rng(5))
        np.testing.assert_array_equal(first, second)
        self.assertTrue(np.all(first >= 0))
        np.testing.assert_array_equal(
            _add_sensor_noise(intensity, 0, np.random.default_rng(5)), intensity
        )

    def test_zero_noise_end_to_end_matches_direct_reconstruction(self):
        pupil, _, _ = pupil_field(64, 16, defocus=0.4)
        sensor = angular_spectrum(pupil, 5e-3)
        recorded = record_hologram(sensor, 20)
        noise_free = _add_sensor_noise(recorded, 0, np.random.default_rng(4))
        reconstructed = reconstruct_field(noise_free, 20, 12)
        direct = reconstruct_field(record_hologram(sensor, 20), 20, 12)
        np.testing.assert_array_equal(reconstructed, direct)
        self.assertTrue(np.iscomplexobj(reconstructed))

    def test_sensor_noise_rejects_invalid_intensity_and_sigma(self):
        rng = np.random.default_rng(1)
        for invalid in (
            np.ones((2, 2), dtype=complex),
            np.ones(4),
            np.array([[np.nan]]),
            np.array([[-1.0]]),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    _add_sensor_noise(invalid, 0.1, rng)
        for sigma in (-0.1, np.nan, np.inf):
            with self.subTest(sigma=sigma):
                with self.assertRaises(ValueError):
                    _add_sensor_noise(np.ones((2, 2)), sigma, rng)

    def test_unknown_grid_requires_explicit_settings(self):
        with self.assertRaisesRegex(ValueError, "specify carrier and window"):
            run_condition(seed=1, n=96, radius=24, sweep_points=3)
        result = run_condition(
            seed=1, n=96, radius=24, carrier=30, window=18, sweep_points=3
        )
        self.assertEqual(result["sideband_settings_source"], "explicit")
        for kwargs in (
            {"carrier": 30.5, "window": 18},
            {"carrier": 31, "window": 18},
            {"carrier": 30, "window": 19},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    run_condition(seed=1, n=96, radius=24, sweep_points=3, **kwargs)

    def test_smoke_benchmark_writes_complete_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results"
            output.mkdir()
            (output / "obsolete.txt").write_text("leave unrelated output alone")
            status = main(["--config", "configs/v0.2.0-smoke.json", "--output", str(output)])
            self.assertEqual(status, 0)
            for name in ("manifest.json", "raw_results.json", "analysis.json", "claims.json", "report.md", "checksums.sha256"):
                self.assertTrue((output / name).exists(), name)
            claims = json.loads((output / "claims.json").read_text())
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(claims["scope"], "synthetic_simulation_only")
            self.assertFalse(claims["physical_claim"])
            self.assertTrue(manifest["source_hashes"])
            self.assertTrue(manifest["config"]["carrier_bins"] == 40)
            self.assertTrue((output / "obsolete.txt").exists())
            json.loads(
                (output / "raw_results.json").read_text(),
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )

if __name__ == "__main__":
    unittest.main()
