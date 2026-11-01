# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
"""Deterministic statistical utilities for synthetic benchmark results.

Bootstrap intervals quantify sampling variability within the specified
synthetic simulation distribution. They are not confidence intervals for
physical repeatability, instrument performance, or real-world generalization.
"""
from __future__ import annotations

import math

import numpy as np


def _values(values):
    array = np.asarray(list(values), dtype=float)
    if array.size == 0 or not np.isfinite(array).all():
        raise ValueError("values must be a non-empty finite numeric sequence")
    return array


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
    if n_bootstrap < 100:
        raise ValueError("n_bootstrap must be at least 100")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
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
    successes = int(successes)
    n = int(n)
    if n <= 0 or successes < 0 or successes > n:
        raise ValueError("require 0 <= successes <= n and n > 0")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    z = float(np.sqrt(2) * _erfinv(1 - alpha))
    p = successes / n
    denominator = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return {
        "estimate": p,
        "lower": max(0.0, centre - half),
        "upper": min(1.0, centre + half),
        "level": 1 - alpha,
        "successes": successes,
        "n": n,
        "method": "wilson_score",
    }


def _erfinv(y):
    if not 0 <= y <= 1:
        raise ValueError("erfinv argument must be in [0, 1]")
    low, high = -6.0, 6.0
    for _ in range(100):
        mid = (low + high) / 2
        if math.erf(mid) < y:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def paired_bootstrap_difference(pairs, *, n_bootstrap=10000, alpha=0.05, seed=0):
    array = np.asarray(list(pairs), dtype=float)
    if array.ndim != 2 or array.shape[1] != 2 or array.size == 0:
        raise ValueError("pairs must be a non-empty (n, 2) array")
    if not np.isfinite(array).all():
        raise ValueError("pairs must be finite")
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
    p = np.asarray(list(p_values), dtype=float)
    if p.size == 0 or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("p_values must be finite and within [0, 1]")
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
    for value in (p_null, p_alternative):
        if not 0 <= value <= 1:
            raise ValueError("proportions must be within [0, 1]")
    if p_null == p_alternative:
        return {"achievable": False, "reason": "null and alternative proportions are equal"}
    z_alpha = float(np.sqrt(2) * _erfinv(1 - alpha))
    z_power = float(np.sqrt(2) * _erfinv(power))
    delta = abs(p_alternative - p_null)
    n = ((z_alpha * math.sqrt(p_null * (1 - p_null)) + z_power * math.sqrt(p_alternative * (1 - p_alternative))) / delta) ** 2
    return {
        "achievable": True,
        "p_null": p_null,
        "p_alternative": p_alternative,
        "alpha": alpha,
        "target_power": power,
        "required_n_per_group": int(math.ceil(n)),
        "approximation": "normal_approximation_two_proportion",
    }


def claim_gate(results, decision_rules):
    if not isinstance(results, dict) or not isinstance(decision_rules, dict):
        raise ValueError("results and decision_rules must be dictionaries")
    checks = []
    for name, rule in decision_rules.items():
        if not callable(rule):
            raise ValueError(f"decision rule {name!r} must be callable")
        checks.append({"rule": name, "passed": bool(rule(results))})
    all_pass = all(item["passed"] for item in checks)
    return {
        "claim_gate_status": "pass" if all_pass else "fail",
        "checks": checks,
    }
