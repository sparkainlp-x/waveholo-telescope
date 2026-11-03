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
    power_analysis_proportion,
    wilson_interval,
)


class TestStatistics(unittest.TestCase):
    def test_median_and_iqr(self):
        result = median_and_iqr([1, 2, 3, 4, 5])
        self.assertEqual(result["median"], 3.0)
        self.assertEqual(result["iqr"], 2.0)

    def test_bootstrap_is_seed_reproducible(self):
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        first = bootstrap_median_interval(values, n_bootstrap=500, seed=7)
        second = bootstrap_median_interval(values, n_bootstrap=500, seed=7)
        self.assertEqual(first, second)

    def test_wilson_zero_and_all_successes(self):
        zero = wilson_interval(0, 10)
        all_success = wilson_interval(10, 10)
        self.assertEqual(zero["lower"], 0.0)
        self.assertEqual(all_success["upper"], 1.0)

    def test_benjamini_hochberg_monotone(self):
        adjusted = benjamini_hochberg([0.001, 0.008, 0.039, 0.041, 0.2])
        self.assertTrue(np.all(np.diff(adjusted[adjusted.argsort()]) >= -1e-12))

    def test_power_analysis(self):
        result = power_analysis_proportion(0.05, 0.15, alpha=0.05, power=0.8)
        self.assertTrue(result["achievable"])
        self.assertGreater(result["required_n_per_group"], 0)


class TestClaims(unittest.TestCase):
    def test_passing_result_is_synthetic_only(self):
        results = {
            "primary": {
                "phase_rms_median": 0.005,
                "success_fraction": {"estimate": 1.0, "n": 20},
            },
            "null_control": {"phase_rms": 0.004},
        }
        evaluated = evaluate(results)
        self.assertEqual(evaluated["claim_gate_status"], "pass")
        self.assertEqual(evaluated["scope"], "synthetic_simulation_only")
        self.assertFalse(evaluated["physical_claim"])

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


if __name__ == "__main__":
    unittest.main()
