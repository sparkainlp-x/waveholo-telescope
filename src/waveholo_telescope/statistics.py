# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
"""Deterministic statistical utilities for synthetic benchmark results.

Bootstrap intervals quantify sampling variability within the specified
synthetic simulation distribution. They are not confidence intervals for
physical repeatability, instrument performance, or real-world generalization.
"""
from __future__ import annotations

import math
from numbers import Integral, Real
from statistics import NormalDist

import numpy as np


def _real(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        value = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return value


def _integer(value, name, minimum=0):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _probability(value, name, *, closed=False):
    value = _real(value, name)
    if not (0 <= value <= 1 if closed else 0 < value < 1):
        raise ValueError(f"{name} must be {'within [0, 1]' if closed else 'between 0 and 1'}")
    return value


def _values(values, *, paired=False):
    try:
        array = np.asarray(list(values), dtype=object)
    except (TypeError, ValueError) as exc:
        raise ValueError("values must be a finite numeric sequence") from exc
    valid_shape = array.ndim == 2 and array.shape[1] == 2 if paired else array.ndim == 1
    if not valid_shape or array.size == 0:
        raise ValueError("pairs must have shape (n, 2)" if paired else "values must be a non-empty one-dimensional sequence")
    return np.array([_real(value, "values") for value in array.flat]).reshape(array.shape)


def _bootstrap_parameters(n_bootstrap, alpha, seed):
    return (
        _integer(n_bootstrap, "n_bootstrap", 100),
        _probability(alpha, "alpha"),
        _integer(seed, "seed"),
    )


def median_and_iqr(values):
    array = _values(values)
    q1, median, q3 = np.quantile(array, [0.25, 0.5, 0.75])
    return {
        "n": int(array.size),
        "median": float(median),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(q3 - q1),
        "min": float(array.min()),
        "max": float(array.max()),
    }


def bootstrap_median_interval(values, *, n_bootstrap=10000, alpha=0.05, seed=0):
    n_bootstrap, alpha, seed = _bootstrap_parameters(n_bootstrap, alpha, seed)
    array = _values(values)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, array.size, size=(n_bootstrap, array.size))
    medians = np.median(array[indices], axis=1)
    lower, upper = np.quantile(medians, [alpha / 2, 1 - alpha / 2])
    return {
        "estimate": float(np.median(array)),
        "lower": float(lower),
        "upper": float(upper),
        "level": 1 - alpha,
        "n_bootstrap": int(n_bootstrap),
        "seed": int(seed),
        "method": "percentile_bootstrap_median",
    }


def wilson_interval(successes, n, alpha=0.05):
    successes = _integer(successes, "successes")
    n = _integer(n, "n", 1)
    if successes > n:
        raise ValueError("require 0 <= successes <= n and n > 0")
    alpha = _probability(alpha, "alpha")
    z = NormalDist().inv_cdf(1 - alpha / 2)
    p = successes / n
    denominator = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return {
        "estimate": p,
        "lower": 0.0 if successes == 0 else max(0.0, centre - half),
        "upper": 1.0 if successes == n else min(1.0, centre + half),
        "level": 1 - alpha,
        "successes": successes,
        "n": n,
        "method": "wilson_score",
    }


def paired_bootstrap_difference(pairs, *, n_bootstrap=10000, alpha=0.05, seed=0):
    n_bootstrap, alpha, seed = _bootstrap_parameters(n_bootstrap, alpha, seed)
    array = _values(pairs, paired=True)
    differences = array[:, 0] - array[:, 1]
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, differences.size, size=(n_bootstrap, differences.size))
    bootstrap = differences[indices].mean(axis=1)
    lower, upper = np.quantile(bootstrap, [alpha / 2, 1 - alpha / 2])
    return {
        "estimate": float(differences.mean()),
        "lower": float(lower),
        "upper": float(upper),
        "level": 1 - alpha,
        "n": int(differences.size),
        "n_bootstrap": int(n_bootstrap),
        "seed": int(seed),
        "method": "paired_percentile_bootstrap_mean_difference",
    }


def benjamini_hochberg(p_values, q=0.05):
    p = _values(p_values)
    if ((p < 0) | (p > 1)).any():
        raise ValueError("p_values must be finite and within [0, 1]")
    q = _real(q, "q")
    if not 0 < q <= 1:
        raise ValueError("q must be in (0, 1]")
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * p.size / np.arange(1, p.size + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0, 1)
    result = np.empty_like(adjusted)
    result[order] = adjusted
    return result


def power_analysis_proportion(p_null, p_alternative, alpha=0.05, power=0.8):
    """Uncorrected two-sided normal approximation, equal-allocation iid Bernoulli groups."""
    p_null = _probability(p_null, "p_null", closed=True)
    p_alternative = _probability(p_alternative, "p_alternative", closed=True)
    alpha = _probability(alpha, "alpha")
    power = _probability(power, "power")
    if p_null == p_alternative:
        return {"achievable": False, "reason": "null and alternative proportions are equal"}
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    z_power = NormalDist().inv_cdf(power)
    pooled = (p_null + p_alternative) / 2
    delta = abs(p_alternative - p_null)
    n = ((z_alpha * math.sqrt(2 * pooled * (1 - pooled)) + z_power * math.sqrt(p_null * (1 - p_null) + p_alternative * (1 - p_alternative))) / delta) ** 2
    return {
        "achievable": True,
        "p_null": p_null,
        "p_alternative": p_alternative,
        "alpha": alpha,
        "target_power": power,
        "required_n_per_group": int(math.ceil(n)),
        "approximation": "normal_approximation_two_proportion",
        "design": "two-sided equal-allocation independent iid Bernoulli groups",
        "continuity_correction": False,
    }


def claim_gate(results, decision_rules):
    if not isinstance(results, dict) or not isinstance(decision_rules, dict):
        raise ValueError("results and decision_rules must be dictionaries")
    checks = []
    for name, rule in decision_rules.items():
        if not callable(rule):
            raise ValueError(f"decision rule {name!r} must be callable")
        try:
            outcome = rule(results)
            passed = isinstance(outcome, bool) and outcome
        except Exception:
            passed = False
        checks.append({"rule": name, "passed": passed})
    all_pass = bool(checks) and all(item["passed"] for item in checks)
    return {
        "claim_gate_status": "pass" if all_pass else "fail",
        "checks": checks,
    }
