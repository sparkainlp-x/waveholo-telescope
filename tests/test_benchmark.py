# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
import json
import hashlib
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from waveholo_telescope.analysis import focus_sweep, parabolic_peak
from waveholo_telescope.benchmark import (
    main, run_condition, run_benchmark, _write_json, _add_sensor_noise,
)
from waveholo_telescope.hologram import record_hologram, reconstruct_field
from waveholo_telescope.metrics import eroded_mask, phase_rms_error
from waveholo_telescope.propagation import angular_spectrum
from waveholo_telescope.pupil import pupil_field, pupil_grid
from waveholo_telescope.provenance import source_hashes


class TestBenchmark(unittest.TestCase):
    def config(self):
        return json.loads((Path(__file__).resolve().parents[1]
                           / "configs/v0.2.0-smoke.json").read_text())

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
            self.assertNotEqual(claims["scientific_verdict"], "pass")
            for line in (output / "checksums.sha256").read_text().splitlines():
                digest, filename = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((output / filename).read_bytes()).hexdigest(), digest)
            manifest = json.loads((output / "manifest.json").read_text())
            analysis = json.loads((output / "analysis.json").read_text())
            self.assertEqual(manifest["acceptance"], analysis["acceptance"])
            self.assertEqual(manifest["acceptance"], claims["acceptance"])
            with self.assertRaises(ValueError):
                main(["--config", "smoke", "--output", str(output)])

    def test_reconstruction_output_is_consumed_by_measurement(self):
        known, _, _ = pupil_field(64, 16, defocus=0.1)
        known = angular_spectrum(known, 0.005)
        with patch("waveholo_telescope.benchmark.reconstruct_field", return_value=known), \
                patch("waveholo_telescope.benchmark.focus_sweep", wraps=focus_sweep) as sweep, \
                patch("waveholo_telescope.benchmark.angular_spectrum",
                      wraps=angular_spectrum) as propagate:
            run_condition(seed=11, n=64, radius=16, noise_sigma=0, sweep_points=3)
        self.assertIs(sweep.call_args.args[0], known)
        reverse = [call for call in propagate.call_args_list if call.args[1] < 0]
        self.assertEqual(len(reverse), 4)
        for call in reverse[:3]:
            self.assertIs(call.args[0], known)
        self.assertIsNot(reverse[-1].args[0], known)  # Deliberately incorrect control.

    def test_known_field_and_incorrect_intensity_negative_control(self):
        pupil, _, phase = pupil_field(128, 32, defocus=0.4, astig_x=0.3, coma_x=0.2)
        sensor = angular_spectrum(pupil, 0.005)
        intensity = record_hologram(sensor, 40)
        base = reconstruct_field(intensity, 40, 24)
        rho, _, _ = pupil_grid(128, 32)
        mask = eroded_mask(rho, 32, 2)
        correct = phase_rms_error(angular_spectrum(base, -0.005), phase, mask)
        incorrect = phase_rms_error(angular_spectrum(intensity, -0.005), phase, mask)
        self.assertLess(correct, 0.03)
        self.assertGreater(incorrect, 0.1)
        row = run_condition(seed=11, noise_sigma=0, sweep_points=3)
        self.assertAlmostEqual(row["phase_rms_true_focus_waves"], correct)
        self.assertAlmostEqual(row["intensity_propagation_rms_true_focus_waves"], incorrect)

    def test_plane_wave_sideband_and_propagation(self):
        _, x = np.mgrid[:64, :64]
        field = 0.5 * np.exp(2j * np.pi * 2 * x / 64 + 0.3j)
        reconstructed = reconstruct_field(record_hologram(field, 20), 20, 12)
        np.testing.assert_allclose(reconstructed, field, atol=1e-14)
        np.testing.assert_allclose(
            angular_spectrum(angular_spectrum(field, 0.005), -0.005), field, atol=1e-12
        )

    def test_primary_condition_and_nondefault_thresholds(self):
        config = self.config()
        config.update(primary_noise_sigma=0.0, primary_rms_threshold=0.02,
                      min_success_fraction=0.5)
        _, analysis = run_benchmark(config)
        self.assertEqual(analysis["primary"]["noise_sigma"], 0.0)
        self.assertEqual(analysis["primary"]["threshold"], 0.02)
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_bytes(json.dumps(config, indent=2).replace("\n", "\r\n").encode())
            output = Path(directory) / "result"
            main(["--config", str(config_path), "--output", str(output)])
            claims = json.loads((output / "claims.json").read_text())
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["config_sha256"],
                             hashlib.sha256(config_path.read_bytes()).hexdigest())
            self.assertTrue(manifest["coarse_prior_equals_simulated_truth"])
            self.assertEqual(claims["acceptance"], analysis["acceptance"])
            self.assertEqual(claims["claim_gate_status"], "pass")
            self.assertNotEqual(claims["scientific_verdict"], "pass")
            self.assertIn("0.020000", (output / "report.md").read_text())

    def test_invalid_configuration_rejected_before_fft(self):
        invalid = {
            "seeds": [[11, 11], [True], [1.5], []],
            "noise_levels": [[0.0, 0.0], [float("nan")], [True], []],
            "primary_noise_sigma": [float("inf"), True, 0.123],
            "grid": [True, 128.5],
            "pupil_radius_px": [True, 32.5],
            "sweep_points": [True, 2, 3.5],
            "n_bootstrap": [True, 99, 100.5],
            "true_distance_m": [True, -1, float("nan")],
            "primary_rms_threshold": [True, -1, float("inf")],
            "min_success_fraction": [True, -1, 1.1],
            "scope": ["physical"],
            "carrier_bins": [True, 64, 40.5],
            "sideband_half_width_bins": [True, 64, 24.5],
            "schema_version": ["1.0", "unknown"],
        }
        for key, values in invalid.items():
            for value in values:
                config = copy.deepcopy(self.config())
                config[key] = value
                with self.subTest(key=key, value=value), patch("numpy.fft.fft2") as fft:
                    with self.assertRaises(ValueError):
                        run_benchmark(config)
                    fft.assert_not_called()
        config = self.config()
        del config["primary_noise_sigma"]
        with self.assertRaises(ValueError):
            run_benchmark(config)

    def test_search_range_does_not_follow_truth(self):
        for mode, extra in [
            ("local_refinement", {"coarse_distance_m": 0.005}),
            ("blind_acquisition", {"coarse_distance_m": None, "search_range_m": [0.002, 0.008]}),
        ]:
            first = run_condition(seed=11, n=64, radius=16, sweep_points=3,
                                  acquisition_mode=mode, **extra)
            second = run_condition(seed=11, n=64, radius=16, sweep_points=3,
                                   true_distance_m=0.006, acquisition_mode=mode, **extra)
            self.assertEqual(first["search_range_m"], second["search_range_m"])
        with self.assertRaises(ValueError):
            run_condition(seed=11, acquisition_mode="blind_acquisition")

    def test_strict_json_and_source_inventory(self):
        self.assertIn("benchmark.py", source_hashes())
        with patch("pathlib.Path.rglob", return_value=iter([])):
            with self.assertRaises(RuntimeError):
                source_hashes()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                _write_json(Path(directory) / "invalid.json", {"value": float("nan")})
            for content in ('{"seeds": [], "seeds": [11]}', '{"value": NaN}',
                            '{"value": Infinity}', '{"value": 1e309}'):
                config = Path(directory) / "config.json"
                config.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    main(["--config", str(config), "--output", str(Path(directory) / "out")])

    def test_sensor_noise_preserves_real_zero_noise_and_rejects_complex(self):
        hologram = np.arange(16, dtype=float).reshape(4, 4)
        np.testing.assert_array_equal(
            _add_sensor_noise(hologram, 0, np.random.default_rng(11)), hologram
        )
        first = _add_sensor_noise(hologram, 0.05, np.random.default_rng(11))
        second = _add_sensor_noise(hologram, 0.05, np.random.default_rng(11))
        np.testing.assert_array_equal(first, second)
        with self.assertRaises(ValueError):
            _add_sensor_noise(hologram.astype(complex), 0, np.random.default_rng(11))

    def test_peak_missing_diagnostics_are_json_safe(self):
        result = parabolic_peak([0, 1, 2], [3, 2, 1])
        self.assertIsNone(result["curvature_per_m2"])
        json.dumps(result, allow_nan=False)
        for distances in ([1, 1, 2], [2, 1, 0], [-1, 0, 1]):
            with self.assertRaises(ValueError):
                parabolic_peak(distances, [1, 2, 1])

    def test_packaged_presets_match_explicit_configs(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("smoke", "primary"):
            external = json.loads((root / "configs" / f"v0.2.0-{name}.json").read_text())
            packaged = json.loads((root / "src/waveholo_telescope/configs"
                                   / f"v0.2.0-{name}.json").read_text())
            self.assertEqual(packaged, external)


if __name__ == "__main__":
    unittest.main()
