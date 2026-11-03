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
import csv
import json
import platform
import resource
import time
import subprocess
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


def _add_sensor_noise(hologram, sigma_relative, rng, *, clip_negative=True):
    hologram = np.asarray(hologram)
    if np.iscomplexobj(hologram) or hologram.ndim != 2 or not np.isfinite(hologram).all():
        raise ValueError("hologram must be a finite real 2D intensity array")
    hologram = np.asarray(hologram, dtype=float)
    if not np.isfinite(sigma_relative) or sigma_relative < 0:
        raise ValueError("sigma_relative must be finite and non-negative")
    if sigma_relative == 0:
        return hologram.copy()
    noisy = hologram + rng.normal(0.0, sigma_relative * hologram.mean(), hologram.shape)
    return np.clip(noisy, 0.0, None) if clip_negative else noisy


def run_condition(*, seed, n=128, radius=32, true_distance_m=5.0e-3,
                  carrier=CAR_DEFAULT, window=WIN_DEFAULT,
                  noise_sigma=0.05, sweep_half_range_m=1.0e-3,
                  sweep_points=21, aberration_scale=1.0,
                  clip_negative_intensity=True):
    started = time.perf_counter()
    if n < 64 or radius <= 0 or radius >= n // 2:
        raise ValueError("require n >= 64 and 0 < radius < n/2")
    if sweep_points < 3:
        raise ValueError("sweep_points must be at least 3")
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
    noisy_hologram = _add_sensor_noise(
        hologram, noise_sigma, rng, clip_negative=clip_negative_intensity
    )
    input_checksum = hashlib.sha256(
        np.ascontiguousarray(noisy_hologram).tobytes()
    ).hexdigest()
    baseband = reconstruct_field(noisy_hologram, carrier, window)

    distances = np.linspace(
        max(0.0, true_distance_m - sweep_half_range_m),
        true_distance_m + sweep_half_range_m,
        sweep_points,
    )
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

    return {
        "seed": int(seed),
        "input_checksum": input_checksum,
        "runtime_seconds": time.perf_counter() - started,
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
                clip_negative_intensity=bool(config.get("clip_negative_intensity", True)),
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
        clip_negative_intensity=bool(config.get("clip_negative_intensity", True)),
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


def _write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _commit_sha(root):
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _working_tree_clean(root):
    try:
        result = subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return not result.strip()


def _summary_row(metric, values, seed, n_bootstrap):
    values = np.asarray(values, dtype=float)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError(f"{metric} must contain finite values")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, values.size, size=(n_bootstrap, values.size))
    means = values[indices].mean(axis=1)
    lower, upper = np.quantile(means, [0.025, 0.975])
    return {
        "metric": metric,
        "n": int(values.size),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "standard_deviation": float(values.std(ddof=1)) if values.size > 1 else 0.0,
        "ci95_mean_lower": float(lower),
        "ci95_mean_upper": float(upper),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "ci_method": "percentile bootstrap mean",
    }


def _write_summary_figure(path, summary_rows, raw, timestamp):
    rows = [row for row in summary_rows if row["metric"].startswith("phase_rms_measured_focus_waves@")]
    if not rows:
        return
    noises = [float(row["metric"].split("=", 1)[1]) for row in rows]
    medians = [row["median"] for row in rows]
    upper = [row["ci95_mean_upper"] for row in rows]
    lower = [row["ci95_mean_lower"] for row in rows]
    width, height = 760, 440
    left, right, top, bottom = 85, 25, 45, 80
    xmax = max(noises) or 1.0
    ymax = max(max(upper), 1e-12) * 1.1
    points, marks = [], []
    for noise, median, lo, hi in zip(noises, medians, lower, upper):
        x = left + (width - left - right) * noise / xmax
        y = height - bottom - (height - top - bottom) * median / ymax
        ylo = height - bottom - (height - top - bottom) * lo / ymax
        yhi = height - bottom - (height - top - bottom) * hi / ymax
        points.append(f"{x:.1f},{y:.1f}")
        marks.append(
            f'<path d="M{x:.1f},{ylo:.1f} V{yhi:.1f}" stroke="#225ea8"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#225ea8"/>'
            f'<text x="{x:.1f}" y="{height-bottom+20}" text-anchor="middle" font-size="12">{noise:g}</text>'
        )
    n = len(raw) // max(len(noises), 1)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{width/2}" y="22" text-anchor="middle" font-size="15">SYNTHETIC pupil simulation; {timestamp}</text>
<text x="{width/2}" y="{height-18}" text-anchor="middle" font-size="13">Relative additive Gaussian noise sigma</text>
<text transform="translate(20 {height/2}) rotate(-90)" text-anchor="middle" font-size="13">Residual RMS wavefront error (waves)</text>
<path d="M{left},{top} V{height-bottom} H{width-right}" fill="none" stroke="#333"/>
<polyline points="{" ".join(points)}" fill="none" stroke="#225ea8" stroke-width="2"/>
{''.join(marks)}
<text x="{left}" y="{height-45}" font-size="11">Median shown; bars are bootstrap 95% CI for mean; N={n}/condition. Current simplified Gaussian model; no telescope validation.</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run deterministic synthetic waveholo-telescope benchmark")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
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

    root = Path(__file__).resolve().parents[2]
    commit = _commit_sha(root)
    tree_clean = _working_tree_clean(root)
    provenance_ok = bool(commit) and tree_clean
    provenance_check = {"rule": "identified_clean_commit", "passed": provenance_ok}
    claims["claim_gate_checks"].append(provenance_check)
    if not provenance_ok:
        claims["claim_gate_status"] = "fail"
        claims["headline"] = headline(claims)
    timestamp = datetime.now(timezone.utc).isoformat()
    config_sha = _sha256(config_path)
    seed_values = [int(value) for value in config["seeds"]]
    bootstrap_count = int(config.get("n_bootstrap", 2000))
    summary_rows = []
    for metric, field in (
        ("focus_error_m", "focus_error_m"),
        ("phase_rms_measured_focus_waves", "phase_rms_measured_focus_waves"),
        ("phase_agreement", "phase_agreement"),
    ):
        for noise in config["noise_levels"]:
            selected = [row for row in raw if row["noise_sigma"] == float(noise)]
            summary_rows.append(_summary_row(
                f"{metric}@noise_sigma={float(noise):g}",
                [row[field] for row in selected],
                seed_values[0],
                bootstrap_count,
            ))
    for row in summary_rows:
        row.update({
            "protocol_version": config.get("protocol_version", "PROTOCOL-v1.0.0"),
            "code_commit_sha": commit,
            "timestamp_utc": timestamp,
            "config_json": json.dumps(config, sort_keys=True),
            "input_checksum": config_sha,
            "software_versions": json.dumps({"python": sys.version.split()[0], "numpy": np.__version__}, sort_keys=True),
            "input_checksums": json.dumps([row["input_checksum"] for row in raw]),
            "random_seeds": json.dumps(seed_values),
        })

    per_seed_rows = []
    metric_rows = []
    for row in raw:
        flat = {
            "protocol_version": config.get("protocol_version", "PROTOCOL-v1.0.0"),
            "code_commit_sha": commit,
            "timestamp_utc": timestamp,
            "config_json": json.dumps(config, sort_keys=True),
            "input_checksum": config_sha,
            "software_versions": json.dumps({"python": sys.version.split()[0], "numpy": np.__version__}, sort_keys=True),
            "seed": row["seed"],
            "hologram_checksum": row["input_checksum"],
            "runtime_seconds": row["runtime_seconds"],
            "noise_sigma": row["noise_sigma"],
            "grid": row["grid"],
            "pupil_radius_px": row["pupil_radius_px"],
            "carrier_bins": row["carrier_bins"],
            "sideband_half_width_bins": row["sideband_half_width_bins"],
            "true_distance_m": row["true_distance_m"],
            "focus_error_m": row["focus_error_m"],
            "focus_at_boundary": row["focus"]["at_boundary"],
            "phase_rms_measured_focus_waves": row["phase_rms_measured_focus_waves"],
            "phase_rms_true_focus_waves": row["phase_rms_true_focus_waves"],
            "phase_agreement": row["phase_agreement"],
        }
        per_seed_rows.append(flat)
        for metric in (
            "focus_error_m",
            "phase_rms_measured_focus_waves",
            "phase_rms_true_focus_waves",
            "phase_agreement",
        ):
            metric_rows.append({
                "protocol_version": flat["protocol_version"],
                "code_commit_sha": commit,
                "timestamp_utc": timestamp,
                "config_json": json.dumps(config, sort_keys=True),
                "input_checksum": config_sha,
                "software_versions": json.dumps({"python": sys.version.split()[0], "numpy": np.__version__}, sort_keys=True),
                "seed": flat["seed"],
                "hologram_checksum": row["input_checksum"],
                "runtime_seconds": row["runtime_seconds"],
                "noise_sigma": flat["noise_sigma"],
                "metric": metric,
                "value": flat[metric],
                "unit": "m" if metric == "focus_error_m" else (
                    "waves" if "waves" in metric else "dimensionless"
                ),
            })

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "package_version": "0.2.0",
        "protocol_version": config.get("protocol_version", "PROTOCOL-v1.0.0"),
        "repository_url": "https://github.com/sparkainlp-x/waveholo-telescope",
        "code_commit_sha": commit or None,
        "status": "COMPLETE" if provenance_ok else "INVALID",
        "working_tree_clean": tree_clean,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "generated_at_utc": timestamp,
        "random_seeds": seed_values,
        "config": config,
        "input_checksums": {
            "config": config_sha,
            "holograms": [row["input_checksum"] for row in raw],
        },
        "source_hashes": _source_hashes(),
        "runtime_seconds": time.perf_counter() - started,
        "cpu": platform.processor() or platform.machine(),
        "peak_memory_bytes": int(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            * (1024 if platform.system() == "Linux" else 1)
        ),
        "output_checksums": {},
    }

    _write_json(output / "manifest.json", manifest)
    _write_json(output / "raw_results.json", raw)
    _write_json(output / "analysis.json", analysis)
    _write_json(output / "claims.json", claims)
    _write_json(output / "summary.json", {"protocol_version": manifest["protocol_version"], "metrics": summary_rows})
    _write_json(output / "environment.json", {
        "python_version": sys.version,
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "cpu": platform.processor() or platform.machine(),
        "peak_memory_bytes": int(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            * (1024 if platform.system() == "Linux" else 1)
        ),
    })
    (output / "code_commit.txt").write_text((commit or "UNIDENTIFIED") + "\n", encoding="utf-8")
    _write_csv(output / "per_seed_results.csv", per_seed_rows, list(per_seed_rows[0]))
    _write_csv(output / "metrics.csv", metric_rows, list(metric_rows[0]))
    _write_csv(output / "summary.csv", summary_rows, list(summary_rows[0]))
    figure_dir = output / "figures"
    figure_dir.mkdir(exist_ok=True)
    _write_summary_figure(figure_dir / "phase_rms_vs_noise.svg", summary_rows, raw, timestamp)

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

    manifest["runtime_seconds"] = time.perf_counter() - started
    result_files = [
        path for path in sorted(item for item in output.rglob("*") if item.is_file())
        if path.name not in {"manifest.json", "checksums.sha256", "raw_checksums.sha256"}
    ]
    manifest["output_checksums"] = {
        path.relative_to(output).as_posix(): _sha256(path) for path in result_files
    }
    _write_json(output / "manifest.json", manifest)
    (output / "raw_checksums.sha256").write_text(
        "\n".join(f"{_sha256(path)}  {path.relative_to(output).as_posix()}" for path in result_files) + "\n",
        encoding="utf-8",
    )
    checksum_lines = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if path.name == "checksums.sha256":
            continue
        checksum_lines.append(f"{_sha256(path)}  {path.relative_to(output).as_posix()}")
    (output / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"Benchmark complete: {output}")
    return 0 if commit and claims["claim_gate_status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
