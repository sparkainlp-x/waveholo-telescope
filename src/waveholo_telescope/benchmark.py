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
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .analysis import focus_sweep, parabolic_peak
from .claims import evaluate, headline
from .hologram import record_hologram, reconstruct_field
from .metrics import eroded_mask, phase_agreement, phase_rms_error, phase_variance
from .propagation import CAR_DEFAULT, DX, WL, WIN_DEFAULT, angular_spectrum
from .pupil import pupil_field, pupil_grid
from .statistics import bootstrap_median_interval, median_and_iqr, wilson_interval

SCHEMA_VERSION = "1.0"


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_hashes():
    root = Path(__file__).resolve().parents[2]
    hashes = {}
    for path in sorted((root / "src" / "waveholo_telescope").glob("*.py")):
        hashes[str(path.relative_to(root))] = _sha256(path)
    return hashes


def _add_sensor_noise(hologram, sigma_relative, rng):
    hologram = np.asarray(hologram, dtype=float)
    if sigma_relative < 0:
        raise ValueError("sigma_relative must be non-negative")
    if sigma_relative == 0:
        return hologram.copy()
    noisy = hologram + rng.normal(0.0, sigma_relative * hologram.mean(), hologram.shape)
    return np.clip(noisy, 0.0, None)


def run_condition(*, seed, n=128, radius=32, true_distance_m=5.0e-3,
                  carrier=CAR_DEFAULT, window=WIN_DEFAULT,
                  noise_sigma=0.05, sweep_half_range_m=1.0e-3,
                  sweep_points=21, aberration_scale=1.0):
    if n < 64 or radius <= 0 or radius >= n // 2:
        raise ValueError("require n >= 64 and 0 < radius < n/2")
    if sweep_points < 3:
        raise ValueError("sweep_points must be at least 3")
    # Keep the library defaults usable for the small grids used by unit tests.
    # The production configuration supplies its own carrier/window values.
    if carrier == CAR_DEFAULT and window == WIN_DEFAULT:
        window = min(window, max(1, n // 4 - 1))
        carrier = min(carrier, n // 2 - window - 1)
    if not (0 < carrier < n // 2):
        raise ValueError("carrier must satisfy 0 < carrier < n/2")
    if not (0 <= window < n // 2) or carrier + window > n // 2:
        raise ValueError("sideband window must fit within the centred Fourier spectrum")
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
    sweep_distances, contrasts = focus_sweep(noisy_hologram, mask, distances, dx=DX, wl=WL)
    focus = parabolic_peak(sweep_distances, contrasts)
    measured_distance = focus["refined_distance_m"]

    reconstructed_measured = angular_spectrum(noisy_hologram, -measured_distance, dx=DX, wl=WL)
    reconstructed_true = angular_spectrum(noisy_hologram, -true_distance_m, dx=DX, wl=WL)
    rho, _, _ = pupil_grid(n, radius)
    eroded = eroded_mask(rho, radius, 2)

    rms_measured = phase_rms_error(reconstructed_measured, true_phase, eroded)
    rms_true = phase_rms_error(reconstructed_true, true_phase, eroded)
    agreement = phase_agreement(reconstructed_measured, true_phase, eroded)
    edge_field = angular_spectrum(noisy_hologram, -float(sweep_distances[-1]), dx=DX, wl=WL)

    return {
        "seed": int(seed),
        "noise_sigma": float(noise_sigma),
        "grid": int(n),
        "pupil_radius_px": int(radius),
        "carrier_bins": int(carrier),
        "sideband_half_width_bins": int(window),
        "true_distance_m": float(true_distance_m),
        "focus": focus,
        "focus_error_m": float(measured_distance - true_distance_m),
        "phase_rms_measured_focus_waves": rms_measured,
        "phase_rms_true_focus_waves": rms_true,
        "phase_agreement": agreement,
        "aperture_contrast_at_sampled_peak": focus["score"],
        "phase_variance_at_sweep_edge": phase_variance(edge_field),
        "phase_variance_locates_focus": False,
    }


def run_benchmark(config):
    required = {"seeds", "noise_levels", "grid", "pupil_radius_px", "true_distance_m"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"benchmark config missing keys: {sorted(missing)}")
    seeds = [int(seed) for seed in config["seeds"]]
    noise_levels = [float(value) for value in config["noise_levels"]]
    if not seeds or not noise_levels or any(value < 0 for value in noise_levels):
        raise ValueError("seeds and noise_levels must be non-empty; noise must be non-negative")

    raw = []
    for noise in noise_levels:
        for seed in seeds:
            raw.append(run_condition(
                seed=seed,
                n=int(config["grid"]),
                radius=int(config["pupil_radius_px"]),
                true_distance_m=float(config["true_distance_m"]),
                carrier=int(config.get("carrier_bins", CAR_DEFAULT)),
                window=int(config.get("sideband_half_width_bins", WIN_DEFAULT)),
                noise_sigma=noise,
                sweep_half_range_m=float(config.get("sweep_half_range_m", 1.0e-3)),
                sweep_points=int(config.get("sweep_points", 21)),
                aberration_scale=float(config.get("aberration_scale", 1.0)),
            ))

    primary_noise = noise_levels[-1]
    primary = [row for row in raw if row["noise_sigma"] == primary_noise]
    rms_values = [row["phase_rms_measured_focus_waves"] for row in primary]
    threshold = float(config.get("primary_rms_threshold", 0.01))
    successes = sum(value <= threshold for value in rms_values)

    null = run_condition(
        seed=seeds[0],
        n=int(config["grid"]),
        radius=int(config["pupil_radius_px"]),
        true_distance_m=float(config["true_distance_m"]),
        carrier=int(config.get("carrier_bins", CAR_DEFAULT)),
        window=int(config.get("sideband_half_width_bins", WIN_DEFAULT)),
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
                n_bootstrap=int(config.get("n_bootstrap", 2000)),
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
            "locates_focus": False,
            "note": "phase_variance does not locate the pupil plane for this phase-object configuration",
        },
    }
    return raw, analysis


def _write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run deterministic synthetic waveholo-telescope benchmark")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))

    raw, analysis = run_benchmark(config)
    claims = evaluate({
        "primary": analysis["primary"],
        "null_control": analysis["null_control"],
        "scope": "synthetic_simulation_only",
    })
    claims["headline"] = headline(claims)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "package_version": "0.2.0",
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "config_sha256": _sha256(config_path),
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
        "- `phase_variance` does not locate the pupil plane in this phase-object configuration.",
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


if __name__ == "__main__":
    raise SystemExit(main())
