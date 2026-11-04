# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
"""Conservative claim gating for synthetic waveholo-telescope results.

No gate outcome authorizes a claim about a physical telescope, camera,
atmosphere, adaptive-optics system, or observatory deployment.
"""
from __future__ import annotations

from copy import deepcopy
import math

from .acceptance import resolve_acceptance
from .statistics import _integer, _probability, _real, claim_gate

SCOPE = "synthetic_simulation_only"


def _nonnegative(value):
    try:
        return _real(value, "RMS") >= 0
    except ValueError:
        return False


def _success_fraction(primary):
    fraction = primary.get("success_fraction", {})
    estimate = _probability(fraction.get("estimate"), "success fraction", closed=True)
    if "n" in fraction or "successes" in fraction:
        n = _integer(fraction.get("n"), "n", 1)
        successes = _integer(fraction.get("successes"), "successes")
        if successes > n or not math.isclose(estimate, successes / n, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("success fraction is inconsistent with counts")
        if "n" in primary and _integer(primary["n"], "primary n", 1) != n:
            raise ValueError("primary n conflicts with success counts")
    elif "n" in primary:
        _integer(primary["n"], "primary n", 1)
    return estimate


def default_rules(primary_rms_threshold=0.01, min_success_fraction=0.9):
    thresholds = resolve_acceptance({
        "primary_rms_threshold": primary_rms_threshold,
        "min_success_fraction": min_success_fraction,
    })

    def primary_rms(results):
        value = results.get("primary", {}).get("phase_rms_median")
        return _nonnegative(value) and _real(value, "RMS") <= thresholds["primary_rms_threshold"]

    def null_control(results):
        return _nonnegative(results.get("null_control", {}).get("phase_rms"))

    def replication(results):
        return _success_fraction(results.get("primary", {})) >= thresholds["min_success_fraction"]

    def scope(results):
        return results.get("scope") == SCOPE

    def acceptance_consistent(results):
        primary = results.get("primary", {})
        if "threshold" in primary:
            reported = _real(primary["threshold"], "primary threshold")
            if reported != thresholds["primary_rms_threshold"]:
                return False
        if "acceptance" in results:
            reported = resolve_acceptance({"acceptance": results["acceptance"]})
            if any(reported[name] != thresholds[name] for name in results["acceptance"]):
                return False
        return True

    return {
        "primary_rms_within_threshold": primary_rms,
        "null_control_reported": null_control,
        "replication_threshold_met": replication,
        "synthetic_scope_declared": scope,
        "acceptance_thresholds_consistent": acceptance_consistent,
    }


def evaluate(results, *, primary_rms_threshold=0.01, min_success_fraction=0.9):
    if not isinstance(results, dict):
        raise ValueError("results must be a dictionary")
    results = deepcopy(results)
    results.setdefault("scope", SCOPE)
    acceptance = resolve_acceptance({
        "primary_rms_threshold": primary_rms_threshold,
        "min_success_fraction": min_success_fraction,
    })
    gate = claim_gate(results, default_rules(**acceptance))
    results["acceptance"] = acceptance
    results["claim_gate_status"] = gate["claim_gate_status"]
    results["claim_gate_checks"] = gate["checks"]
    results["physical_claim"] = False
    # Smoke metrics alone do not verify a frozen protocol or scientific controls.
    results["scientific_verdict"] = "inconclusive" if gate["claim_gate_status"] == "pass" else "fail"
    results["scientific_evidence_status"] = "not_established"
    results["scientific_evidence"] = {
        "frozen_protocol_verification": "UNRUN",
        "scientific_control_evaluation": "UNRUN",
    }
    results["preregistered"] = False
    results["scientific_claim"] = False
    for name in ("protocol", "control_evidence"):
        if name in results:
            results[name] = {"verification_status": "UNRUN"}
    for name in ("scientific_claim_text", "scientific_headline"):
        results.pop(name, None)
    return results


def headline(results):
    status = results.get("claim_gate_status", "fail")
    if status == "pass":
        return (
            "Under the specified synthetic pupil and holography configuration, "
            "the pipeline met the configured smoke-benchmark phase-RMS and "
            "replication checks. Scientific evidence is not established; "
            "this is not evidence about a physical telescope."
        )
    return "The synthetic benchmark did not meet its configured smoke criteria; no positive scientific claim is supported."
