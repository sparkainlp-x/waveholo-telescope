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
import importlib.metadata
import importlib.resources
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .analysis import focus_sweep, parabolic_peak
from .claims import evaluate, headline
from .hologram import record_hologram, reconstruct_field
from .metrics import eroded_mask, phase_agreement, phase_rms_error, phase_variance
from .propagation import DX, WL, angular_spectrum
from .pupil import pupil_field, pupil_grid
from .statistics import bootstrap_median_interval, median_and_iqr, wilson_interval

SCHEMA_VERSION = "1.0"
GRID_PRESETS = {256: (80, 48), 128: (40, 24), 64: (20, 12)}
ARTIFACT_NAMES = (
    "manifest.json", "raw_results.json", "analysis.json", "claims.json",
    "report.md", "checksums.sha256",
)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_hashes():
    package_dir = Path(__file__).resolve().parent
    hashes = {}
    for path in sorted(package_dir.glob("*.py")):
        hashes[f"waveholo_telescope/{path.name}"] = _sha256(path)
    if not hashes or not all(hashes.values()):
        raise RuntimeError("installed package source hashes are unavailable")
    return hashes


def _add_sensor_noise(hologram, sigma_relative, rng):
    if np.iscomplexobj(hologram):
        raise ValueError("sensor noise must be applied to real intensity data")
    hologram = np.asarray(hologram, dtype=float)
    try:
        sigma_relative = float(sigma_relative)
    except (TypeError, ValueError):
        raise ValueError("sigma_relative must be finite and non-negative") from None
    if (hologram.ndim != 2 or not np.isfinite(hologram).all()
            or (hologram < 0).any()):
        raise ValueError("hologram must be finite, non-negative 2D intensity data")
    if not np.isfinite(sigma_relative) or sigma_relative < 0:
        raise ValueError("sigma_relative must be finite and non-negative")
    if sigma_relative == 0:
        return hologram.copy()
    noisy = hologram + rng.normal(0.0, sigma_relative * hologram.mean(), hologram.shape)
    return np.clip(noisy, 0.0, None)


def _integer(value, name, minimum):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return int(value)


def _resolved_sideband_settings(n, carrier, window):
    preset = GRID_PRESETS.get(n)
    if carrier is None and window is None:
        if preset is None:
            raise ValueError(
                f"grid {n} has no documented preset; specify carrier and window explicitly"
            )
        carrier, window = preset
        source = "documented_grid_preset"
    elif carrier is None or window is None:
        raise ValueError("carrier and window must be supplied together")
    else:
        source = "explicit"
    carrier = _integer(carrier, "carrier", 1)
    window = _integer(window, "window", 0)
    if carrier >= n // 2:
        raise ValueError("carrier must satisfy 0 < carrier < grid/2")
    if window >= n // 2:
        raise ValueError("window must satisfy 0 <= window < grid/2")
    if carrier + window > n // 2:
        raise ValueError("sideband window does not fit in the centered Fourier array")
    return carrier, window, source


def run_condition(*, seed, n=128, radius=32, true_distance_m=5.0e-3,
                  carrier=None, window=None, noise_sigma=0.05,
                  sweep_half_range_m=1.0e-3, sweep_points=21,
                  aberration_scale=1.0):
    n = _integer(n, "n", 64)
    radius = _integer(radius, "radius", 1)
    seed = _integer(seed, "seed", 0)
    sweep_points = _integer(sweep_points, "sweep_points", 3)
    if radius >= n // 2:
        raise ValueError("require n >= 64 and 0 < radius < n/2")
    carrier, window, settings_source = _resolved_sideband_settings(n, carrier, window)
    numeric = {
        "true_distance_m": true_distance_m,
        "sweep_half_range_m": sweep_half_range_m,
        "noise_sigma": noise_sigma,
        "aberration_scale": aberration_scale,
    }
    for name, value in numeric.items():
        try:
            numeric[name] = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be finite") from None
        if not np.isfinite(numeric[name]):
            raise ValueError(f"{name} must be finite")
    true_distance_m = numeric["true_distance_m"]
    sweep_half_range_m = numeric["sweep_half_range_m"]
    noise_sigma = numeric["noise_sigma"]
    aberration_scale = numeric["aberration_scale"]
    if true_distance_m < 0 or sweep_half_range_m <= 0 or noise_sigma < 0:
        raise ValueError("distance and noise settings must be non-negative; sweep range must be positive")
    if aberration_scale < 0:
        raise ValueError("aberration_scale must be non-negative")
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

    distances = np.linspace(
        max(0.0, true_distance_m - sweep_half_range_m),
        true_distance_m + sweep_half_range_m,
        sweep_points,
    )
    sweep_distances, contrasts = focus_sweep(baseband, mask, distances, dx=DX, wl=WL)
    focus = parabolic_peak(sweep_distances, contrasts)
    measured_distance = focus["refined_distance_m"]
    variances = [
        phase_variance(angular_spectrum(baseband, -float(distance), dx=DX, wl=WL))
        for distance in sweep_distances
    ]
    variance_index = int(np.argmin(variances))
    variance_distance = float(sweep_distances[variance_index])
    localization_error = variance_distance - true_distance_m
    resolution = focus["resolution_half_step_m"]
    variance_localizes_focus = (
        abs(localization_error) <= resolution if resolution is not None
        else bool(np.isclose(localization_error, 0.0))
    )

    reconstructed_measured = angular_spectrum(baseband, -measured_distance, dx=DX, wl=WL)
    reconstructed_true = angular_spectrum(baseband, -true_distance_m, dx=DX, wl=WL)
    rho, _, _ = pupil_grid(n, radius)
    eroded = eroded_mask(rho, radius, 2)

    rms_measured = phase_rms_error(reconstructed_measured, true_phase, eroded)
    rms_true = phase_rms_error(reconstructed_true, true_phase, eroded)
    agreement = phase_agreement(reconstructed_measured, true_phase, eroded)

    return {
        "seed": seed,
        "noise_sigma": noise_sigma,
        "grid": n,
        "pupil_radius_px": radius,
        "carrier_bins": carrier,
        "sideband_half_width_bins": window,
        "sideband_settings_source": settings_source,
        "fourier_crop_fits_array": True,
        "sideband_separation_verified": False,
        "true_distance_m": true_distance_m,
        "focus": focus,
        "focus_error_m": float(measured_distance - true_distance_m),
        "phase_rms_measured_focus_waves": rms_measured,
        "phase_rms_true_focus_waves": rms_true,
        "phase_agreement": agreement,
        "aperture_contrast_at_sampled_peak": focus["score"],
        "phase_variance_sweep": [float(value) for value in variances],
        "phase_variance_minimum": {
            "distance_m": variance_distance,
            "value": float(variances[variance_index]),
            "at_boundary": bool(variance_index in (0, len(variances) - 1)),
            "localization_error_m": float(localization_error),
            "localizes_focus": bool(variance_localizes_focus),
        },
    }


def run_benchmark(config):
    if not isinstance(config, dict):
        raise ValueError("benchmark config must be a JSON object")
    required = {"seeds", "noise_levels", "grid", "pupil_radius_px", "true_distance_m"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"benchmark config missing keys: {sorted(missing)}")
    n = _integer(config["grid"], "grid", 64)
    radius = _integer(config["pupil_radius_px"], "pupil_radius_px", 1)
    carrier, window, settings_source = _resolved_sideband_settings(
        n, config.get("carrier_bins"), config.get("sideband_half_width_bins")
    )
    if radius >= n // 2:
        raise ValueError("pupil_radius_px must be less than grid/2")
    if not isinstance(config["seeds"], list) or not isinstance(config["noise_levels"], list):
        raise ValueError("seeds and noise_levels must be arrays")
    seeds = [_integer(seed, "seed", 0) for seed in config["seeds"]]
    try:
        noise_levels = [float(value) for value in config["noise_levels"]]
    except (TypeError, ValueError):
        raise ValueError("noise_levels must be finite non-negative numbers") from None
    if (not seeds or not noise_levels
            or any(not np.isfinite(value) or value < 0 for value in noise_levels)):
        raise ValueError("seeds and noise_levels must be non-empty; noise must be non-negative")
    sweep_points = _integer(config.get("sweep_points", 21), "sweep_points", 3)
    n_bootstrap = _integer(config.get("n_bootstrap", 2000), "n_bootstrap", 100)
    try:
        true_distance = float(config["true_distance_m"])
        sweep_half_range = float(config.get("sweep_half_range_m", 1e-3))
        aberration_scale = float(config.get("aberration_scale", 1.0))
        threshold = float(config.get("primary_rms_threshold", 0.01))
        min_success_fraction = float(config.get("min_success_fraction", 0.9))
    except (TypeError, ValueError):
        raise ValueError("numeric benchmark settings must be finite numbers") from None
    for key, value in {
        "true_distance_m": true_distance,
        "sweep_half_range_m": sweep_half_range,
        "aberration_scale": aberration_scale,
        "primary_rms_threshold": threshold,
        "min_success_fraction": min_success_fraction,
    }.items():
        if not np.isfinite(value):
            raise ValueError(f"{key} must be finite")
    if true_distance < 0 or sweep_half_range <= 0 or aberration_scale < 0:
        raise ValueError("distance and aberration settings are out of range")
    if threshold < 0 or not 0 <= min_success_fraction <= 1:
        raise ValueError("claim thresholds are out of range")
    acceptance_profile = config.get("acceptance_profile", "smoke")
    if acceptance_profile not in {"smoke", "scientific"}:
        raise ValueError("acceptance_profile must be 'smoke' or 'scientific'")
    resolved_config = dict(config)
    resolved_config.update({
        "grid": n,
        "pupil_radius_px": radius,
        "carrier_bins": carrier,
        "sideband_half_width_bins": window,
        "sideband_settings_source": settings_source,
        "true_distance_m": true_distance,
        "noise_levels": noise_levels,
        "seeds": seeds,
        "sweep_half_range_m": sweep_half_range,
        "sweep_points": sweep_points,
        "aberration_scale": aberration_scale,
        "primary_rms_threshold": threshold,
        "min_success_fraction": min_success_fraction,
        "n_bootstrap": n_bootstrap,
        "acceptance_profile": acceptance_profile,
    })

    raw = []
    for noise in noise_levels:
        for seed in seeds:
            raw.append(run_condition(
                seed=seed,
                n=n,
                radius=radius,
                true_distance_m=true_distance,
                carrier=carrier,
                window=window,
                noise_sigma=noise,
                sweep_half_range_m=sweep_half_range,
                sweep_points=sweep_points,
                aberration_scale=aberration_scale,
            ))

    primary_noise = noise_levels[-1]
    primary = [row for row in raw if row["noise_sigma"] == primary_noise]
    rms_values = [row["phase_rms_measured_focus_waves"] for row in primary]
    successes = sum(value <= threshold for value in rms_values)
    variance_localized = [
        row["phase_variance_minimum"]["localizes_focus"] for row in primary
    ]
    variance_errors = [
        row["phase_variance_minimum"]["localization_error_m"] for row in primary
    ]
    if all(variance_localized):
        variance_decision = "locates_focus"
    elif not any(variance_localized):
        variance_decision = "does_not_locate_focus"
    else:
        variance_decision = "mixed"

    null = run_condition(
        seed=seeds[0],
        n=n,
        radius=radius,
        true_distance_m=true_distance,
        carrier=carrier,
        window=window,
        noise_sigma=0.0,
        aberration_scale=0.0,
    )

    analysis = {
        "schema_version": SCHEMA_VERSION,
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
            "decision": variance_decision,
            "localized_trials": int(sum(variance_localized)),
            "trials": len(variance_localized),
            "localization_error_m": median_and_iqr(variance_errors),
            "decision_rule": "the minimum is localized when its sampled distance is within half the smallest sweep interval of true distance",
        },
        "resolved_configuration": resolved_config,
    }
    return raw, analysis


def _write_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _load_config(spec):
    candidate = Path(spec)
    if candidate.is_file():
        content = candidate.read_bytes()
        return json.loads(content), content, str(candidate.resolve())
    preset = Path(spec).stem.removeprefix("v0.2.0-")
    if preset not in {"smoke", "primary"}:
        raise FileNotFoundError(f"configuration not found: {spec}")
    resource = importlib.resources.files("waveholo_telescope").joinpath(
        "configs", f"v0.2.0-{preset}.json"
    )
    content = resource.read_bytes()
    return json.loads(content), content, f"package:configs/v0.2.0-{preset}.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run deterministic synthetic waveholo-telescope benchmark")
    parser.add_argument("--config", required=True, help="config path or packaged preset: smoke/primary")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACT_NAMES:
        artifact = output / name
        if artifact.is_file() or artifact.is_symlink():
            artifact.unlink()
    config, config_bytes, config_origin = _load_config(args.config)
    raw, analysis = run_benchmark(config)
    resolved_config = analysis["resolved_configuration"]
    claims = evaluate({
        "primary": analysis["primary"],
        "null_control": analysis["null_control"],
    }, primary_rms_threshold=resolved_config["primary_rms_threshold"],
       min_success_fraction=resolved_config["min_success_fraction"],
       acceptance_profile=resolved_config["acceptance_profile"])
    claims["headline"] = headline(claims)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "package_version": importlib.metadata.version("waveholo-telescope"),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_origin": config_origin,
        "config": resolved_config,
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "resolved_geometry": {
            "grid": resolved_config["grid"],
            "pupil_radius_px": resolved_config["pupil_radius_px"],
            "carrier_bins": resolved_config["carrier_bins"],
            "sideband_half_width_bins": resolved_config["sideband_half_width_bins"],
            "fourier_crop_fits_array": True,
            "sideband_separation_verified": False,
        },
        "source_hashes": _source_hashes(),
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
        f"- Success fraction: {analysis['primary']['success_fraction']['estimate']:.3f}",
        "",
        "## Negative control",
        "",
        f"- Null-control phase RMS at true focus: {analysis['null_control']['phase_rms']:.6f} waves",
        f"- Measured phase-variance focus decision: {analysis['phase_variance_negative_control']['decision']} "
        f"({analysis['phase_variance_negative_control']['localized_trials']}/"
        f"{analysis['phase_variance_negative_control']['trials']} primary trials localized).",
        "",
        "## Scope",
        "",
        "Synthetic simulation only. No physical telescope, camera, atmosphere, adaptive-optics, or observatory claim is supported.",
        "",
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")

    checksum_lines = [
        f"{_sha256(output / name)}  {name}"
        for name in ARTIFACT_NAMES if name != "checksums.sha256"
    ]
    (output / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"Benchmark complete: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
