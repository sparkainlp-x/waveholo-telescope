# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
"""Deterministic synthetic benchmark engine for waveholo-telescope.

All results compare a reconstructed synthetic pupil wavefront with known
injected Zernike aberrations. No result validates a physical telescope,
camera, atmosphere, adaptive-optics system, or observatory deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from importlib.resources import files
from numbers import Real
from pathlib import Path

import numpy as np

from .analysis import focus_sweep, parabolic_peak
from .acceptance import resolve_acceptance
from .claims import evaluate, headline
from .hologram import record_hologram, reconstruct_field
from .metrics import eroded_mask, phase_agreement, phase_rms_error, phase_variance
from .propagation import DX, WL, angular_spectrum
from .provenance import canonical_hash, provenance, source_hashes
from .pupil import pupil_field, pupil_grid
from .statistics import bootstrap_median_interval, median_and_iqr, wilson_interval

SCHEMA_VERSION = "2.0"


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_hashes():
    return source_hashes()


def _integer(value, name, minimum=0):
    if (not isinstance(value, (int, np.integer)) or isinstance(value, (bool, np.bool_))
            or value < minimum):
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _number(value, name, minimum=0):
    if (not isinstance(value, Real) or isinstance(value, (bool, np.bool_))
            or not np.isfinite(value) or value < minimum):
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return float(value)


def _resolve_sampling(n, carrier, window):
    _integer(n, "grid", 64)
    if (carrier is None) != (window is None):
        raise ValueError("carrier and sideband window must be supplied together")
    if carrier is None:
        presets = {64: (20, 12), 128: (40, 24), 256: (80, 48)}
        if n not in presets:
            raise ValueError("non-preset grids require explicit carrier and window")
        carrier, window = presets[n]
    _integer(carrier, "carrier", 1)
    _integer(window, "window")
    if carrier >= n / 2 or window >= n / 2 or carrier + window > n / 2:
        raise ValueError("carrier and sideband window must fit in the Fourier spectrum")
    return int(carrier), int(window)


def _search_distances(mode, coarse, search_range, half_range, points):
    _integer(points, "sweep_points", 3)
    half_range = _number(half_range, "sweep_half_range_m")
    if half_range == 0:
        raise ValueError("sweep_half_range_m must be positive")
    if mode == "local_refinement":
        if search_range is not None:
            raise ValueError("local refinement uses coarse_distance_m, not search_range_m")
        coarse = _number(coarse, "coarse_distance_m")
        low, high = max(0.0, coarse - half_range), coarse + half_range
    elif mode == "blind_acquisition":
        if coarse is not None:
            raise ValueError("blind acquisition must not use a coarse distance")
        if not isinstance(search_range, (list, tuple)) or len(search_range) != 2:
            raise ValueError("blind acquisition requires an independently fixed search_range_m")
        low, high = [_number(v, "search_range_m") for v in search_range]
        if low >= high:
            raise ValueError("search_range_m must be increasing")
    else:
        raise ValueError("unknown acquisition_mode")
    return np.linspace(low, high, points)


def _add_sensor_noise(hologram, sigma_relative, rng):
    if np.iscomplexobj(hologram):
        raise ValueError("sensor noise requires recorded real intensity, not a complex field")
    hologram = np.asarray(hologram, dtype=float)
    sigma_relative = _number(sigma_relative, "sigma_relative")
    if not np.isfinite(hologram).all() or (hologram < 0).any():
        raise ValueError("hologram must be finite and non-negative")
    if sigma_relative == 0:
        return hologram.copy()
    noisy = hologram + rng.normal(0.0, sigma_relative * hologram.mean(), hologram.shape)
    return np.clip(noisy, 0.0, None)


def run_condition(*, seed, n=128, radius=32, true_distance_m=5.0e-3,
                  carrier=None, window=None,
                  noise_sigma=0.05, sweep_half_range_m=1.0e-3,
                  sweep_points=21, aberration_scale=1.0,
                  acquisition_mode="local_refinement", coarse_distance_m=5.0e-3,
                  search_range_m=None):
    _integer(seed, "seed")
    carrier, window = _resolve_sampling(n, carrier, window)
    _integer(radius, "pupil radius", 1)
    true_distance_m = _number(true_distance_m, "true_distance_m")
    noise_sigma = _number(noise_sigma, "noise_sigma")
    aberration_scale = _number(aberration_scale, "aberration_scale")
    if n < 64 or radius <= 0 or radius >= n // 2:
        raise ValueError("require n >= 64 and 0 < radius < n/2")
    distances = _search_distances(
        acquisition_mode, coarse_distance_m, search_range_m, sweep_half_range_m, sweep_points
    )
    rng = np.random.default_rng(seed)

    pupil, mask, true_phase = pupil_field(
        n,
        radius,
        defocus=0.4 * aberration_scale,
        astig_x=0.3 * aberration_scale,
        coma_x=0.2 * aberration_scale,
    )
    sensor = angular_spectrum(pupil, true_distance_m, dx=DX, wl=WL)
    hologram = record_hologram(sensor, carrier)
    noisy_hologram = _add_sensor_noise(hologram, noise_sigma, rng)
    baseband = reconstruct_field(noisy_hologram, carrier, window)

    sweep_distances, contrasts = focus_sweep(baseband, mask, distances, dx=DX, wl=WL)
    focus = parabolic_peak(sweep_distances, contrasts)
    measured_distance = focus["refined_distance_m"]

    reconstructed_measured = angular_spectrum(baseband, -measured_distance, dx=DX, wl=WL)
    reconstructed_true = angular_spectrum(baseband, -true_distance_m, dx=DX, wl=WL)
    rho, _, _ = pupil_grid(n, radius)
    eroded = eroded_mask(rho, radius, 2)

    rms_measured = phase_rms_error(reconstructed_measured, true_phase, eroded)
    rms_true = phase_rms_error(reconstructed_true, true_phase, eroded)
    agreement = phase_agreement(reconstructed_measured, true_phase, eroded)
    edge_field = angular_spectrum(baseband, -float(sweep_distances[-1]), dx=DX, wl=WL)
    intensity_control = angular_spectrum(noisy_hologram, -true_distance_m, dx=DX, wl=WL)

    return {
        "seed": int(seed),
        "noise_sigma": float(noise_sigma),
        "grid": int(n),
        "pupil_radius_px": int(radius),
        "carrier_bins": int(carrier),
        "sideband_half_width_bins": int(window),
        "true_distance_m": float(true_distance_m),
        "acquisition_mode": acquisition_mode,
        "search_range_m": [float(distances[0]), float(distances[-1])],
        "coarse_distance_m": float(coarse_distance_m) if coarse_distance_m is not None else None,
        "focus": focus,
        "focus_error_m": float(measured_distance - true_distance_m),
        "phase_rms_measured_focus_waves": rms_measured,
        "phase_rms_true_focus_waves": rms_true,
        "phase_agreement": agreement,
        "aperture_contrast_at_sampled_peak": focus["score"],
        "phase_variance_at_sweep_edge": phase_variance(edge_field),
        "intensity_propagation_rms_true_focus_waves": phase_rms_error(
            intensity_control, true_phase, eroded
        ),
    }


def run_benchmark(config):
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    if config.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError(f"benchmark config requires schema_version {SCHEMA_VERSION}")
    try:
        canonical_hash(config)
    except (TypeError, ValueError) as exc:
        raise ValueError("config must contain only finite JSON values") from exc
    required = {"seeds", "noise_levels", "primary_noise_sigma", "grid",
                "pupil_radius_px", "true_distance_m"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"benchmark config missing keys: {sorted(missing)}")
    if config.get("scope", "synthetic_simulation_only") != "synthetic_simulation_only":
        raise ValueError("conflicting benchmark scope")
    if not isinstance(config["seeds"], list) or not isinstance(config["noise_levels"], list):
        raise ValueError("seeds and noise_levels must be lists")
    seeds = [_integer(seed, "seed") for seed in config["seeds"]]
    noise_levels = [_number(value, "noise level") for value in config["noise_levels"]]
    if (not seeds or not noise_levels or len(set(seeds)) != len(seeds)
            or len(set(noise_levels)) != len(noise_levels)):
        raise ValueError("seeds and noise_levels must be non-empty and unique")
    primary_noise = _number(config["primary_noise_sigma"], "primary_noise_sigma")
    if primary_noise not in noise_levels:
        raise ValueError("primary_noise_sigma must identify a configured noise condition")
    acceptance = resolve_acceptance(config)
    threshold = acceptance["primary_rms_threshold"]
    n_bootstrap = _integer(config.get("n_bootstrap", 2000), "n_bootstrap", 100)
    mode = config.get("acquisition_mode", "local_refinement")
    if mode == "local_refinement" and "coarse_distance_m" not in config:
        raise ValueError("local refinement requires a supplied coarse_distance_m")
    common = {
        "n": config["grid"],
        "radius": config["pupil_radius_px"],
        "true_distance_m": config["true_distance_m"],
        "carrier": config.get("carrier_bins"),
        "window": config.get("sideband_half_width_bins"),
        "sweep_half_range_m": config.get("sweep_half_range_m", 1.0e-3),
        "sweep_points": config.get("sweep_points", 21),
        "acquisition_mode": mode,
        "coarse_distance_m": config.get("coarse_distance_m"),
        "search_range_m": config.get("search_range_m"),
    }

    raw = []
    for noise in noise_levels:
        for seed in seeds:
            raw.append(run_condition(
                seed=seed,
                **common,
                noise_sigma=noise,
                aberration_scale=config.get("aberration_scale", 1.0),
            ))

    primary = [row for row in raw if row["noise_sigma"] == primary_noise]
    rms_values = [row["phase_rms_measured_focus_waves"] for row in primary]
    successes = sum(value <= threshold for value in rms_values)

    null = run_condition(
        seed=seeds[0],
        **common,
        noise_sigma=0.0,
        aberration_scale=0.0,
    )

    analysis = {
        "schema_version": SCHEMA_VERSION,
        "scope": config.get("scope", "synthetic_simulation_only"),
        "evidence_class": "SYNTHETIC",
        "acceptance": acceptance,
        "acquisition_mode": mode,
        "coarse_prior_equals_simulated_truth": (
            common["coarse_distance_m"] == common["true_distance_m"]
            if mode == "local_refinement" else None
        ),
        "primary": {
            "noise_sigma": primary_noise,
            "phase_rms_median": float(np.median(rms_values)),
            "phase_rms_distribution": median_and_iqr(rms_values),
            "phase_rms_bootstrap": bootstrap_median_interval(
                rms_values,
                n_bootstrap=n_bootstrap,
                seed=seeds[0],
            ),
            "success_fraction": wilson_interval(successes, len(rms_values)),
            "threshold": threshold,
        },
        "null_control": {
            "phase_rms": null["phase_rms_true_focus_waves"],
            "control_type": "aberration_free_pupil_not_empty_pupil",
            "interpretation": "synthetic discretization and sideband-window floor",
        },
        "noise_sweep": {
            str(noise): median_and_iqr([
                row["phase_rms_measured_focus_waves"]
                for row in raw if row["noise_sigma"] == noise
            ])
            for noise in noise_levels
        },
        "phase_variance_negative_control": {
            "evidence_status": "PRIOR_FINDING_NOT_RETESTED",
            "note": "Prior documentation reports that phase_variance does not locate the pupil plane; this run records an edge diagnostic only.",
        },
        "intensity_propagation_negative_control": {
            "phase_rms_true_focus_distribution": median_and_iqr([
                row["intensity_propagation_rms_true_focus_waves"] for row in primary
            ]),
            "all_rejected_by_rms_threshold": all(
                row["intensity_propagation_rms_true_focus_waves"] > threshold for row in primary
            ),
            "interpretation": "deliberately incorrect propagation of recorded intensity as a field",
        },
    }
    return raw, analysis


def _write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run deterministic synthetic waveholo-telescope benchmark")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    config_path = (
        files("waveholo_telescope").joinpath("configs", f"v0.2.0-{args.config}.json")
        if args.config in {"smoke", "primary"} else Path(args.config)
    )
    output = Path(args.output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("output must be empty; historical artifacts must not be overwritten")
    output.mkdir(parents=True, exist_ok=True)
    config_bytes = config_path.read_bytes()
    config_text = config_bytes.decode("utf-8")
    config = json.loads(
        config_text, parse_constant=_reject_json_constant, object_pairs_hook=_unique_json_object
    )

    raw, analysis = run_benchmark(config)
    claims = evaluate(analysis, **analysis["acceptance"])
    claims["headline"] = headline(claims)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        **provenance(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "resolved_config_sha256": canonical_hash({
            "config": config, "acceptance": analysis["acceptance"],
        }),
        "acceptance": analysis["acceptance"],
        "evidence_class": "SYNTHETIC",
        "protocol_verification": "UNVERIFIED; no frozen protocol evidence supplied",
        "coarse_prior_equals_simulated_truth": analysis["coarse_prior_equals_simulated_truth"],
    }

    _write_json(output / "manifest.json", manifest)
    _write_json(output / "raw_results.json", raw)
    _write_json(output / "analysis.json", analysis)
    _write_json(output / "claims.json", claims)

    report = [
        "# WaveHolo Telescope Synthetic Benchmark",
        "",
        claims["headline"],
        "",
        "## Primary result",
        "",
        f"- Median phase RMS at measured focus: {analysis['primary']['phase_rms_median']:.6f} waves",
        f"- Acceptance threshold: {analysis['primary']['threshold']:.6f} waves",
        f"- Minimum success fraction: {analysis['acceptance']['min_success_fraction']}",
        f"- Success fraction: {analysis['primary']['success_fraction']['estimate']:.3f}",
        f"- Primary noise sigma: {analysis['primary']['noise_sigma']}",
        f"- Acquisition mode: {analysis['acquisition_mode']} (no blind-acquisition claim from local refinement)",
        f"- Coarse prior equals simulated truth: {analysis['coarse_prior_equals_simulated_truth']}; equal-prior runs provide no independent acquisition evidence.",
        "",
        "## Negative control",
        "",
        f"- Null-control phase RMS at true focus: {analysis['null_control']['phase_rms']:.6f} waves",
        f"- Intensity-propagation control: {analysis['intensity_propagation_negative_control']}",
        "- `phase_variance` focus failure is a prior finding, not retested here.",
        "- The aberration-free pupil control above is not an empty-pupil/null-signal control.",
        "- Empty-pupil, sideband-width sensitivity and full scientific protocol validation: UNRUN.",
        "",
        "## Scope",
        "",
        "Synthetic simulation only. No physical telescope, camera, atmosphere, adaptive-optics, or observatory claim is supported.",
        "",
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")

    checksum_lines = []
    for path in sorted(output.glob("*")):
        if path.name == "checksums.sha256":
            continue
        checksum_lines.append(f"{_sha256(path)}  {path.name}")
    (output / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"Benchmark complete: {output}")
    return 0


def _reject_json_constant(value):
    raise ValueError(f"non-finite JSON constant: {value}")


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


if __name__ == "__main__":
    raise SystemExit(main())
