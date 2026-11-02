# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
"""Conservative claim gating for synthetic waveholo-telescope results.

No gate outcome authorizes a claim about a physical telescope, camera,
atmosphere, adaptive-optics system, or observatory deployment.
"""
from __future__ import annotations

from .statistics import claim_gate

SCOPE = "synthetic_simulation_only"


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and abs(number) != float("inf")


def _thresholds(primary_rms_threshold, min_success_fraction):
    if not _finite(primary_rms_threshold) or float(primary_rms_threshold) < 0:
        raise ValueError("primary_rms_threshold must be finite and non-negative")
    if (not _finite(min_success_fraction)
            or not 0 <= float(min_success_fraction) <= 1):
        raise ValueError("min_success_fraction must be finite and within [0, 1]")
    return float(primary_rms_threshold), float(min_success_fraction)


def default_rules(primary_rms_threshold=0.01, min_success_fraction=0.9,
                  acceptance_profile="smoke"):
    primary_rms_threshold, min_success_fraction = _thresholds(
        primary_rms_threshold, min_success_fraction
    )
    if acceptance_profile not in {"smoke", "scientific"}:
        raise ValueError("acceptance_profile must be 'smoke' or 'scientific'")

    def primary_rms(results):
        primary = results.get("primary")
        if not isinstance(primary, dict) or "phase_rms_median" not in primary:
            return None
        value = primary["phase_rms_median"]
        return _finite(value) and float(value) <= primary_rms_threshold

    def null_control(results):
        control = results.get("null_control")
        if not isinstance(control, dict) or "phase_rms" not in control:
            return None
        return _finite(control["phase_rms"])

    def replication(results):
        primary = results.get("primary")
        fraction = primary.get("success_fraction") if isinstance(primary, dict) else None
        if not isinstance(fraction, dict) or "estimate" not in fraction:
            return None
        value = fraction["estimate"]
        return _finite(value) and 0 <= float(value) <= 1 and float(value) >= min_success_fraction

    def scope(results):
        return results.get("scope") == SCOPE

    rules = {
        "primary_rms_within_threshold": primary_rms,
        "null_control_reported": null_control,
        "replication_threshold_met": replication,
        "synthetic_scope_declared": scope,
    }
    if acceptance_profile == "scientific":
        rules["scientific_protocol_frozen"] = lambda results: None
    return rules


def evaluate(results, *, primary_rms_threshold=0.01, min_success_fraction=0.9,
             acceptance_profile="smoke"):
    if not isinstance(results, dict):
        raise ValueError("results must be a dictionary")
    results["scope"] = SCOPE
    results["acceptance_profile"] = acceptance_profile
    gate = claim_gate(results, default_rules(
        primary_rms_threshold, min_success_fraction, acceptance_profile
    ))
    results["claim_gate_status"] = gate["claim_gate_status"]
    results["claim_gate_checks"] = gate["checks"]
    results["physical_claim"] = False
    return results


def headline(results):
    status = results.get("claim_gate_status", "fail")
    if status == "pass":
        return (
            "Under the specified synthetic pupil and holography configuration, "
            "the pipeline met the configured smoke-benchmark phase-RMS and "
            "replication checks. This is not evidence about a physical telescope."
        )
    if status == "insufficient_evidence":
        return "The available synthetic results are insufficient for the configured claim gate; no positive claim is supported."
    return "The synthetic benchmark did not meet the configured claim-gate criteria; no positive claim is supported."
