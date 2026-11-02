# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
import unittest

import numpy as np

from waveholo_telescope.claims import evaluate, headline
from waveholo_telescope.statistics import (
    benjamini_hochberg,
    bootstrap_median_interval,
    claim_gate,
    median_and_iqr,
    paired_bootstrap_difference,
    power_analysis_proportion,
    wilson_interval,
)
from waveholo_telescope.analysis import focus_sweep, parabolic_peak


class TestStatistics(unittest.TestCase):
    def test_median_and_iqr(self):
        result = median_and_iqr([1, 2, 3, 4, 5])
        self.assertEqual(result["median"], 3.0)
        self.assertEqual(result["iqr"], 2.0)
        single = median_and_iqr([2])
        self.assertEqual((single["median"], single["iqr"]), (2.0, 0.0))

    def test_bootstrap_is_seed_reproducible(self):
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        first = bootstrap_median_interval(values, n_bootstrap=500, seed=7)
        second = bootstrap_median_interval(values, n_bootstrap=500, seed=7)
        self.assertEqual(first, second)
        single = bootstrap_median_interval([2.0], n_bootstrap=100)
        self.assertEqual((single["lower"], single["upper"]), (2.0, 2.0))

    def test_statistics_validate_shapes_counts_and_probabilities(self):
        for kwargs in (
            {"n_bootstrap": 99},
            {"n_bootstrap": 100.5},
            {"alpha": 0},
            {"alpha": np.nan},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    bootstrap_median_interval([1, 2], **kwargs)
        with self.assertRaises(ValueError):
            median_and_iqr([[1, 2], [3, 4]])
        with self.assertRaises(ValueError):
            wilson_interval(2.5, 10)
        with self.assertRaises(ValueError):
            wilson_interval(1, 10.5)
        with self.assertRaises(ValueError):
            wilson_interval(0, 0)
        with self.assertRaises(ValueError):
            wilson_interval(1, 10, alpha=np.nan)
        with self.assertRaises(ValueError):
            paired_bootstrap_difference([[1, 2], [3, 4]], n_bootstrap=10)
        with self.assertRaises(ValueError):
            paired_bootstrap_difference([[1, 2], [3, 4]], alpha=1)
        with self.assertRaises(ValueError):
            paired_bootstrap_difference([[[1, 2]], [[3, 4]]])
        with self.assertRaises(ValueError):
            paired_bootstrap_difference(3)
        with self.assertRaises(ValueError):
            benjamini_hochberg([[0.01, 0.05]])

    def test_paired_difference_is_first_minus_second(self):
        result = paired_bootstrap_difference(
            [[5, 2], [7, 3]], n_bootstrap=1000, seed=10
        )
        self.assertEqual(result["estimate"], 3.5)
        self.assertEqual(result["lower"], 3.0)
        self.assertEqual(result["upper"], 4.0)
        singleton = paired_bootstrap_difference([[4, 4]], n_bootstrap=100)
        self.assertEqual((singleton["estimate"], singleton["lower"], singleton["upper"]),
                         (0.0, 0.0, 0.0))

    def test_wilson_zero_and_all_successes(self):
        zero = wilson_interval(0, 10)
        all_success = wilson_interval(10, 10)
        reference = wilson_interval(5, 10)
        self.assertEqual(zero["lower"], 0.0)
        self.assertEqual(all_success["upper"], 1.0)
        self.assertAlmostEqual(reference["lower"], 0.236593090512564)
        self.assertAlmostEqual(reference["upper"], 0.763406909487436)

    def test_benjamini_hochberg_monotone(self):
        adjusted = benjamini_hochberg([0.001, 0.008, 0.039, 0.041, 0.2])
        self.assertTrue(np.all(np.diff(adjusted[adjusted.argsort()]) >= -1e-12))

    def test_power_analysis(self):
        result = power_analysis_proportion(0.05, 0.15, alpha=0.05, power=0.8)
        self.assertTrue(result["achievable"])
        self.assertEqual(result["required_n_per_group"], 141)
        self.assertEqual(
            result["approximation"],
            "two_sided_normal_approximation_independent_proportions_equal_group_pooled_null",
        )
        self.assertFalse(power_analysis_proportion(0.1, 0.1)["achievable"])
        for kwargs in ({"alpha": 0}, {"power": 1}, {"power": 0.5},
                       {"power": np.nan}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    power_analysis_proportion(0.05, 0.15, **kwargs)

    def test_claim_gate_rejects_empty_rules_and_marks_missing_evidence(self):
        with self.assertRaises(ValueError):
            claim_gate({}, {})
        self.assertEqual(
            claim_gate({}, {"evidence": lambda result: None})["claim_gate_status"],
            "insufficient_evidence",
        )


class TestClaims(unittest.TestCase):
    def test_passing_result_is_synthetic_only(self):
        results = {
            "primary": {
                "phase_rms_median": 0.005,
                "success_fraction": {"estimate": 1.0},
            },
            "null_control": {"phase_rms": 0.004},
        }
        evaluated = evaluate(results)
        self.assertEqual(evaluated["claim_gate_status"], "pass")
        self.assertEqual(evaluated["scope"], "synthetic_simulation_only")
        self.assertFalse(evaluated["physical_claim"])
        scientific = evaluate({
            "primary": {
                "phase_rms_median": 0.005,
                "success_fraction": {"estimate": 1.0},
            },
            "null_control": {"phase_rms": 0.004},
        }, acceptance_profile="scientific")
        self.assertEqual(scientific["claim_gate_status"], "insufficient_evidence")
        self.assertFalse(scientific["physical_claim"])

    def test_failing_result_blocks_claim(self):
        results = {
            "primary": {
                "phase_rms_median": 0.05,
                "success_fraction": {"estimate": 0.2},
            },
            "null_control": {"phase_rms": 0.004},
        }
        evaluated = evaluate(results)
        self.assertEqual(evaluated["claim_gate_status"], "fail")
        self.assertIn("did not meet", headline(evaluated))


class TestFocusAnalysis(unittest.TestCase):
    def test_focus_sweep_rejects_nonmonotonic_distances(self):
        mask = np.zeros((8, 8), dtype=bool)
        mask[:4, :4] = True
        with self.assertRaises(ValueError):
            focus_sweep(np.ones((8, 8)), mask, [0.0, 1.0, 0.5])

    def test_parabolic_peak_supports_irregular_grid_and_flags_plateau(self):
        distances = np.array([0.0, 0.8, 2.0, 3.5])
        scores = 1 - (distances - 1.6) ** 2
        result = parabolic_peak(distances, scores)
        self.assertAlmostEqual(result["refined_distance_m"], 1.6)
        self.assertFalse(result["at_boundary"])
        self.assertTrue(result["refinement_applied"])
        self.assertIsNotNone(result["resolution_half_step_m"])
        flat = parabolic_peak([0, 1, 2], [1, 1, 1])
        self.assertTrue(flat["plateau"])
        self.assertTrue(flat["weak_curvature"])
        self.assertIsNone(flat["curvature_per_m2"])

    def test_parabolic_peak_rejects_nonmonotonic_and_duplicate_distances(self):
        for distances in ([0, 2, 1], [0, 1, 1]):
            with self.subTest(distances=distances):
                with self.assertRaises(ValueError):
                    parabolic_peak(distances, [0, 1, 0])


if __name__ == "__main__":
    unittest.main()
