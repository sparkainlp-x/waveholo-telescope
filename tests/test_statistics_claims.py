# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
import unittest
from copy import deepcopy
from math import ceil, sqrt
from statistics import NormalDist

import numpy as np

from waveholo_telescope.claims import evaluate, headline
from waveholo_telescope.acceptance import resolve_acceptance
from waveholo_telescope.statistics import (
    benjamini_hochberg,
    bootstrap_median_interval,
    claim_gate,
    median_and_iqr,
    paired_bootstrap_difference,
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
        adjusted = benjamini_hochberg([0.2, 0.001, 0.041, 0.008, 0.039])
        np.testing.assert_allclose(adjusted, [0.2, 0.005, 0.05125, 0.02, 0.05125])
        np.testing.assert_allclose(benjamini_hochberg([1, 0, 0.04, 0.04]), [1, 0, 0.0533333333333333, 0.0533333333333333])

    def test_wilson_canonical_reference(self):
        result = wilson_interval(5, 10)
        self.assertAlmostEqual(result["lower"], 0.236593090512564)
        self.assertAlmostEqual(result["upper"], 0.763406909487436)
        self.assertAlmostEqual(wilson_interval(0, 10)["upper"], 0.277532799862889)
        self.assertAlmostEqual(wilson_interval(10, 10)["lower"], 0.722467200137111)
        self.assertEqual(wilson_interval(0, 1)["lower"], 0)
        self.assertEqual(wilson_interval(1, 1)["upper"], 1)

    def test_wilson_rejects_invalid_counts_and_alpha(self):
        for successes, n in [(True, 2), (1, True), (1.0, 2), (1, 2.5), ("1", 2),
                             (-1, 2), (3, 2), (0, 0), (1, float("inf"))]:
            with self.subTest(successes=successes, n=n), self.assertRaises(ValueError):
                wilson_interval(successes, n)
        for alpha in [True, "0.05", 0, 1, -0.1, float("nan"), float("inf")]:
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                wilson_interval(1, 2, alpha)

    def test_bootstrap_helpers_validate_parameters(self):
        for helper, values in [(bootstrap_median_interval, [1, 2, 3]),
                               (paired_bootstrap_difference, [[1, 0], [3, 1]])]:
            for name, bad in [
                ("n_bootstrap", 99), ("n_bootstrap", True), ("n_bootstrap", 100.5),
                ("n_bootstrap", "100"), ("alpha", True), ("alpha", "0.05"),
                ("alpha", 0), ("alpha", 1), ("alpha", float("nan")),
                ("alpha", float("inf")), ("seed", True), ("seed", -1),
                ("seed", 1.5), ("seed", "1"), ("seed", None),
            ]:
                with self.subTest(helper=helper.__name__, name=name, bad=bad), self.assertRaises(ValueError):
                    helper(values, **{name: bad})

    def test_statistics_reject_non_numeric_and_wrong_dimensions(self):
        for helper in [median_and_iqr, bootstrap_median_interval, benjamini_hochberg]:
            for values in [[], [[0.1, 0.2]], [True, 0.2], ["0.1"], [float("nan")],
                           [float("inf")], [0.2 + 0j], None]:
                with self.subTest(helper=helper.__name__, values=values), self.assertRaises(ValueError):
                    helper(values)
        for pairs in [[], [1, 2], [[1]], [[1, 2, 3]], [[[1, 2]]],
                      [[True, 0]], [["1", 0]], [[float("inf"), 0]], None]:
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                paired_bootstrap_difference(pairs)

    def test_bootstrap_reference_and_pairing(self):
        median = bootstrap_median_interval([4, 4, 4], n_bootstrap=100, seed=3)
        self.assertEqual((median["estimate"], median["lower"], median["upper"]), (4, 4, 4))
        pairs = [[4, 1], [8, 5], [2, -1]]
        first = paired_bootstrap_difference(pairs, n_bootstrap=100, seed=3)
        self.assertEqual(first, paired_bootstrap_difference(pairs, n_bootstrap=100, seed=3))
        self.assertEqual((first["estimate"], first["lower"], first["upper"]), (3, 3, 3))

    def test_power_analysis(self):
        result = power_analysis_proportion(0.05, 0.15, alpha=0.05, power=0.8)
        self.assertTrue(result["achievable"])
        pooled = (0.05 + 0.15) / 2
        expected = ceil(((NormalDist().inv_cdf(0.975) * sqrt(2 * pooled * (1 - pooled))
                          + NormalDist().inv_cdf(0.8) * sqrt(0.05 * 0.95 + 0.15 * 0.85)) / 0.1) ** 2)
        self.assertEqual(result["required_n_per_group"], expected)
        self.assertEqual(result["required_n_per_group"], 141)
        self.assertEqual(result["required_n_per_group"],
                         power_analysis_proportion(0.15, 0.05)["required_n_per_group"])
        self.assertIn("two-sided", result["design"])
        self.assertIn("iid Bernoulli", result["design"])
        self.assertFalse(result["continuity_correction"])
        self.assertFalse(power_analysis_proportion(0.2, 0.2)["achievable"])
        self.assertEqual(power_analysis_proportion(0.1, 0.2)["required_n_per_group"], 199)

    def test_power_analysis_validation(self):
        for name in ["p_null", "p_alternative", "alpha", "power"]:
            for bad in [True, "0.1", float("nan"), float("inf"), -0.1, 1.1]:
                kwargs = dict(p_null=0.1, p_alternative=0.2, alpha=0.05, power=0.8)
                kwargs[name] = bad
                with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                    power_analysis_proportion(**kwargs)
        for name in ["alpha", "power"]:
            for bad in [0, 1]:
                with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                    power_analysis_proportion(0.1, 0.2, **{name: bad})

    def test_claim_gate_fails_closed(self):
        self.assertEqual(claim_gate({}, {})["claim_gate_status"], "fail")
        for value in ["true", 1, [], {}, None, np.bool_(True)]:
            with self.subTest(value=value):
                self.assertEqual(claim_gate({}, {"rule": lambda _: value})["claim_gate_status"], "fail")
        def broken(_):
            raise RuntimeError("invalid result")
        self.assertEqual(claim_gate({}, {"rule": broken})["claim_gate_status"], "fail")
        self.assertEqual(claim_gate({}, {"rule": lambda _: True})["claim_gate_status"], "pass")
        with self.assertRaises(ValueError):
            claim_gate({}, {"rule": True})


class TestClaims(unittest.TestCase):
    def valid_result(self):
        return {
            "scope": "synthetic_simulation_only",
            "primary": {
                "phase_rms_median": 0.005,
                "success_fraction": {"estimate": 1.0, "n": 10, "successes": 10},
            },
            "null_control": {"phase_rms": 0.004},
        }

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
        self.assertEqual(evaluated["scientific_verdict"], "inconclusive")
        self.assertNotIn("scope", results)

    def test_scope_conflicts_are_not_overwritten(self):
        for scope in ["physical_telescope", None, "", False]:
            results = self.valid_result()
            results["scope"] = scope
            original = deepcopy(results)
            evaluated = evaluate(results)
            self.assertEqual(evaluated["scope"], scope)
            self.assertEqual(evaluated["claim_gate_status"], "fail")
            self.assertEqual(results, original)

    def test_invalid_claim_metrics_fail_closed(self):
        for section, field, invalid in [
            ("primary", "phase_rms_median", [True, "0.005", -1, float("nan"), float("inf"), None]),
            ("null_control", "phase_rms", [True, "0.004", -1, float("nan"), float("inf"), None]),
        ]:
            for value in invalid:
                result = self.valid_result()
                result[section][field] = value
                with self.subTest(section=section, value=value):
                    self.assertEqual(evaluate(result)["claim_gate_status"], "fail")
        for value in [True, "1", -0.1, 1.1, float("nan"), float("inf"), None]:
            result = self.valid_result()
            result["primary"]["success_fraction"]["estimate"] = value
            with self.subTest(value=value):
                self.assertEqual(evaluate(result)["claim_gate_status"], "fail")
        for section in ["primary", "null_control"]:
            result = self.valid_result()
            result[section] = None
            self.assertEqual(evaluate(result)["claim_gate_status"], "fail")

    def test_inconsistent_counts_fail_closed(self):
        for counts in [
            {"n": 0, "successes": 0}, {"n": 10, "successes": 11},
            {"n": 10, "successes": 9}, {"n": True, "successes": 1},
            {"n": 10.0, "successes": 10}, {"n": 10, "successes": 10.0},
            {"n": 10, "successes": True}, {"n": "10", "successes": 10},
            {"n": 10, "successes": -1}, {"n": 10, "successes": "10"},
            {"n": float("inf"), "successes": 10},
            {"n": float("nan"), "successes": 10},
            {"n": 10}, {"successes": 10}, {"n": -1, "successes": -1},
        ]:
            result = self.valid_result()
            result["primary"]["success_fraction"] = {"estimate": 1.0, **counts}
            with self.subTest(counts=counts):
                self.assertEqual(evaluate(result)["claim_gate_status"], "fail")
        result = self.valid_result()
        result["primary"]["n"] = 11
        self.assertEqual(evaluate(result)["claim_gate_status"], "fail")

    def test_smoke_is_not_scientific_evidence_and_does_not_mutate(self):
        result = self.valid_result()
        result.update(scientific_verdict="pass", protocol={"verified": True},
                      control_evidence={"verified": True}, physical_claim=True,
                      preregistered=True, scientific_claim=True,
                      scientific_claim_text="Scientific benefit proven",
                      scientific_headline="Verified scientific result",
                      scientific_evidence={"frozen_protocol_verification": "verified",
                                           "scientific_control_evaluation": "verified"},
                      extra_analysis={"kept": [1]})
        original = deepcopy(result)
        evaluated = evaluate(result, **resolve_acceptance({}))
        self.assertEqual(evaluated["claim_gate_status"], "pass")
        self.assertEqual(evaluated["scientific_verdict"], "inconclusive")
        self.assertFalse(evaluated["physical_claim"])
        self.assertFalse(evaluated["preregistered"])
        self.assertFalse(evaluated["scientific_claim"])
        self.assertEqual(evaluated["protocol"], {"verification_status": "UNRUN"})
        self.assertEqual(evaluated["control_evidence"], {"verification_status": "UNRUN"})
        self.assertNotIn("scientific_claim_text", evaluated)
        self.assertNotIn("scientific_headline", evaluated)
        self.assertEqual(evaluated["acceptance"], resolve_acceptance({}))
        self.assertEqual(evaluated["scientific_evidence_status"], "not_established")
        self.assertEqual(evaluated["scientific_evidence"], {
            "frozen_protocol_verification": "UNRUN",
            "scientific_control_evaluation": "UNRUN",
        })
        self.assertEqual(evaluated["extra_analysis"], result["extra_analysis"])
        self.assertEqual(result, original)
        evaluated["extra_analysis"]["kept"].append(2)
        self.assertEqual(result, original)
        self.assertNotIn("preregistered", headline(evaluated))
        self.assertIn("not established", headline(evaluated))

    def test_invalid_thresholds_rejected(self):
        for name, values in [
            ("primary_rms_threshold", [True, "0.01", -1, float("nan"), float("inf")]),
            ("min_success_fraction", [True, "0.9", -1, 1.1, float("nan"), float("inf")]),
        ]:
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    evaluate(self.valid_result(), **{name: value})

    def test_reported_acceptance_must_match_applied_thresholds(self):
        result = self.valid_result()
        result["acceptance"] = resolve_acceptance({})
        result["primary"]["threshold"] = 0.01
        self.assertEqual(evaluate(result)["claim_gate_status"], "pass")
        for field in [True, "0.01", -1, float("nan"), 0.02]:
            invalid = deepcopy(result)
            invalid["primary"]["threshold"] = field
            with self.subTest(threshold=field):
                self.assertEqual(evaluate(invalid)["claim_gate_status"], "fail")
        for acceptance in [
            {"primary_rms_threshold": 0.02}, {"min_success_fraction": 0.8},
            {"primary_rms_threshold": True}, None, {"unknown": 1},
        ]:
            invalid = deepcopy(result)
            invalid["acceptance"] = acceptance
            with self.subTest(acceptance=acceptance):
                self.assertEqual(evaluate(invalid)["claim_gate_status"], "fail")

    def test_acceptance_resolver(self):
        self.assertEqual(resolve_acceptance({}),
                         {"primary_rms_threshold": 0.01, "min_success_fraction": 0.9})
        config = {"unrelated": 1, "primary_rms_threshold": 0.02,
                  "acceptance": {"primary_rms_threshold": 0.02, "min_success_fraction": 1}}
        original = deepcopy(config)
        self.assertEqual(resolve_acceptance(config),
                         {"primary_rms_threshold": 0.02, "min_success_fraction": 1.0})
        self.assertEqual(config, original)
        for bad in [
            {"acceptance": {"primary_rms_threshold": 0.02}, "primary_rms_threshold": 0.01},
            {"acceptance": {"min_success_fraction": 0.8}, "min_success_fraction": 0.9},
            {"acceptance": None}, {"acceptance": {"unknown": 1}}, None,
            {"primary_rms_threshold": True}, {"primary_rms_threshold": "0.01"},
            {"primary_rms_threshold": -1}, {"primary_rms_threshold": float("inf")},
            {"min_success_fraction": float("nan")}, {"min_success_fraction": 2},
            {"acceptance": {"min_success_fraction": -1}},
        ]:
            with self.subTest(config=bad), self.assertRaises(ValueError):
                resolve_acceptance(bad)

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
        self.assertEqual(evaluated["scientific_verdict"], "fail")
        self.assertIn("did not meet", headline(evaluated))


if __name__ == "__main__":
    unittest.main()
