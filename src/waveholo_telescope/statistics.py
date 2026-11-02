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
    try:
        array = np.asarray(values, dtype=float)
        if array.ndim == 0 and not np.isscalar(values):
            array = np.asarray(list(values), dtype=float)
    except (TypeError, ValueError):
        array = np.asarray(list(values), dtype=float)
    if array.ndim != 1 or array.size == 0 or not np.isfinite(array).all():
        raise ValueError("values must be a non-empty, one-dimensional finite numeric sequence")
    return array


def _probability(value, name, *, inclusive_zero=True):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be finite and in (0, 1)") from None
    lower_ok = result >= 0 if inclusive_zero else result > 0
    if not np.isfinite(result) or not lower_ok or result >= 1:
        raise ValueError(f"{name} must be finite and in (0, 1)")
    return result


def _count(value, name, minimum):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return int(value)


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
    n_bootstrap = _count(n_bootstrap, "n_bootstrap", 100)
    alpha = _probability(alpha, "alpha", inclusive_zero=False)
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
    successes = _count(successes, "successes", 0)
    n = _count(n, "n", 1)
    if successes > n:
        raise ValueError("require 0 <= successes <= n and n > 0")
    alpha = _probability(alpha, "alpha", inclusive_zero=False)
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
    if not -1 < y < 1:
        raise ValueError("erfinv argument must be in (-1, 1)")
    low, high = -8.0, 8.0
    for _ in range(100):
        mid = (low + high) / 2
        if math.erf(mid) < y:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def paired_bootstrap_difference(pairs, *, n_bootstrap=10000, alpha=0.05, seed=0):
    try:
        array = np.asarray(pairs, dtype=float)
        if array.ndim == 0:
            array = np.asarray(list(pairs), dtype=float)
    except (TypeError, ValueError):
        array = np.asarray(list(pairs), dtype=float)
    if array.ndim != 2 or array.shape[1] != 2 or array.size == 0:
        raise ValueError("pairs must be a non-empty (n, 2) array")
    if not np.isfinite(array).all():
        raise ValueError("pairs must be finite")
    n_bootstrap = _count(n_bootstrap, "n_bootstrap", 100)
    alpha = _probability(alpha, "alpha", inclusive_zero=False)
    # Each paired difference is first column minus second column.
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
    try:
        q = float(q)
    except (TypeError, ValueError):
        raise ValueError("q must be finite and in (0, 1]") from None
    if not np.isfinite(q) or not 0 < q <= 1:
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
    try:
        p_null, p_alternative = float(p_null), float(p_alternative)
    except (TypeError, ValueError):
        raise ValueError("proportions must be finite and within [0, 1]") from None
    if (not np.isfinite(p_null) or not np.isfinite(p_alternative)
            or not 0 <= p_null <= 1 or not 0 <= p_alternative <= 1):
        raise ValueError("proportions must be finite and within [0, 1]")
    alpha = _probability(alpha, "alpha", inclusive_zero=False)
    power = _probability(power, "power", inclusive_zero=False)
    if p_null == p_alternative:
        return {"achievable": False, "reason": "null and alternative proportions are equal"}
    z_alpha = float(np.sqrt(2) * _erfinv(1 - alpha))
    z_power = float(np.sqrt(2) * _erfinv(2 * power - 1))
    delta = abs(p_alternative - p_null)
    pooled_null = (p_null + p_alternative) / 2
    null_sd = math.sqrt(2 * pooled_null * (1 - pooled_null))
    alternative_sd = math.sqrt(
        p_null * (1 - p_null) + p_alternative * (1 - p_alternative)
    )
    n = ((z_alpha * null_sd + z_power * alternative_sd) / delta) ** 2
    return {
        "achievable": True,
        "p_null": p_null,
        "p_alternative": p_alternative,
        "alpha": alpha,
        "target_power": power,
        "required_n_per_group": int(math.ceil(n)),
        "approximation": "two_sided_normal_approximation_independent_proportions_equal_group_pooled_null",
    }


def claim_gate(results, decision_rules):
    if not isinstance(results, dict) or not isinstance(decision_rules, dict):
        raise ValueError("results and decision_rules must be dictionaries")
    if not decision_rules:
        raise ValueError("decision_rules must not be empty")
    checks = []
    for name, rule in decision_rules.items():
        if not callable(rule):
            raise ValueError(f"decision rule {name!r} must be callable")
        outcome = rule(results)
        if outcome is not None and not isinstance(outcome, (bool, np.bool_)):
            raise ValueError(f"decision rule {name!r} must return bool or None")
        checks.append({"rule": name, "passed": None if outcome is None else bool(outcome)})
    if any(item["passed"] is False for item in checks):
        status = "fail"
    elif any(item["passed"] is None for item in checks):
        status = "insufficient_evidence"
    else:
        status = "pass"
    return {
        "claim_gate_status": status,
        "checks": checks,
    }
