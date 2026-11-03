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


def default_rules(primary_rms_threshold=0.01, min_success_fraction=0.9):
    def primary_rms(results):
        return results.get("primary", {}).get("phase_rms_median", 1e9) <= primary_rms_threshold

    def null_control(results):
        return _finite(results.get("null_control", {}).get("phase_rms"))

    def replication(results):
        primary = results.get("primary", {})
        return (
            int(primary.get("success_fraction", {}).get("n", 0)) >= 20
            and primary.get("success_fraction", {}).get("estimate", 0.0) >= min_success_fraction
        )

    def scope(results):
        return results.get("scope") == SCOPE

    return {
        "primary_rms_within_threshold": primary_rms,
        "null_control_reported": null_control,
        "replication_threshold_met": replication,
        "synthetic_scope_declared": scope,
    }


def evaluate(results, *, primary_rms_threshold=0.01, min_success_fraction=0.9):
    results["scope"] = SCOPE
    gate = claim_gate(results, default_rules(primary_rms_threshold, min_success_fraction))
    results["claim_gate_status"] = gate["claim_gate_status"]
    results["claim_gate_checks"] = gate["checks"]
    results["physical_claim"] = False
    return results


def headline(results):
    status = results.get("claim_gate_status", "fail")
    if status == "pass":
        return (
            "Under the specified synthetic pupil and holography configuration, "
            "the pipeline met the preregistered smoke-benchmark phase-RMS and "
            "replication checks. This is not evidence about a physical telescope."
        )
    return "The synthetic benchmark did not meet its preregistered claim-gate criteria; no positive claim is supported."
