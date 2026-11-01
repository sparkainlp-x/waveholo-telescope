"""Demo: WaveHolo's pipeline pointed at a telescope pupil.

A distant star through a circular pupil (radius 64 px) carrying
defocus 0.4, astigmatism-x 0.3, coma-x 0.2 waves is propagated 5.00
mm to a sensor, recorded as an off-axis hologram (carrier 80 bins,
window 48), and reconstructed. Bars, all against synthetic ground
truth (bench parameters identical to waveholo v0.1.5):

- T1 focus recovery: back-propagation sweep 0..10 mm (0.25 mm
  steps); aperture-contrast peak vs the true 5.00 mm, with a
  parabolic refinement from the peak's neighbours.
- T2 wavefront recovery: at the measured focus plane, recovered
  phase vs injected aberration (eroded mask, 2 px; piston
  removed): RMS error in waves, circular agreement.
- T3 null control: zero aberrations through the same pipeline;
  recovered phase RMS at the true plane.
- T4 noise: hologram + Gaussian noise (std 5% of mean hologram,
  clipped at zero like a real sensor), T1 and T2 repeated.
- T5 secondary readout: WaveHolo's phase_variance peak on the
  same sweep, compared against the aperture-contrast peak.

Run from the package root: python3 demo.py
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from waveholo_telescope.hologram import (  # noqa: E402
    record_hologram, reconstruct_field)
from waveholo_telescope.metrics import (  # noqa: E402
    aperture_contrast, eroded_mask, phase_agreement, phase_rms_error,
    phase_variance)
from waveholo_telescope.propagation import (  # noqa: E402
    angular_spectrum)
from waveholo_telescope.pupil import pupil_field, pupil_grid  # noqa: E402

N = 256
RADIUS = 64
Z_TRUE = 5.0e-3
ABERRATIONS = {"defocus": 0.4, "astig_x": 0.3, "coma_x": 0.2}
ERODE = 2


def sweep(base, mask, true_phase, rho):
    """Back-propagation sweep: contrast + phase variance per distance."""
    distances = np.arange(0.0, 10.0e-3 + 1e-12, 0.25e-3)
    contrasts = []
    variances = []
    for d in distances:
        plane = angular_spectrum(base, -float(d))
        contrasts.append(aperture_contrast(plane, mask))
        variances.append(phase_variance(plane))
    contrasts = np.array(contrasts)
    variances = np.array(variances)
    i = int(np.argmax(contrasts))
    peak = float(distances[i])
    if 0 < i < len(distances) - 1:
        y0, y1, y2 = contrasts[i - 1], contrasts[i], contrasts[i + 1]
        denom = y0 - 2 * y1 + y2
        if denom != 0:
            peak = float(distances[i] + 0.5 * (y0 - y2) / denom * 0.25e-3)
    j = int(np.argmin(variances))
    return {
        "distances": distances,
        "contrasts": contrasts,
        "variances": variances,
        "contrast_peak_mm": peak * 1e3,
        "contrast_peak_value": float(contrasts[i]),
        "phase_var_min_mm": float(distances[j]) * 1e3,
        "phase_var_min_value": float(variances[j]),
    }


def wavefront_at(base, distance, mask, true_phase, rho):
    plane = angular_spectrum(base, -float(distance))
    emask = eroded_mask(rho, RADIUS, ERODE)
    return (phase_rms_error(plane, true_phase, emask),
            phase_agreement(plane, true_phase, emask))


def run_pipeline(aberrations, hologram_noise=0.0, seed=42):
    field, mask, true_phase = pupil_field(N, RADIUS, **aberrations)
    sensor = angular_spectrum(field, Z_TRUE)
    holo = record_hologram(sensor)
    if hologram_noise > 0.0:
        rng = np.random.default_rng(seed)
        holo = np.clip(
            holo + rng.normal(0.0, hologram_noise * holo.mean(),
                              size=holo.shape),
            0.0, None)
    base = reconstruct_field(holo)
    rho, _, _ = pupil_grid(N, RADIUS)
    return base, mask, true_phase, rho


def main():
    print(f"Pupil: radius {RADIUS} px, aberrations (waves) {ABERRATIONS}")
    print(f"True pupil->sensor distance: {Z_TRUE * 1e3:.2f} mm")
    base, mask, true_phase, rho = run_pipeline(ABERRATIONS)
    result = sweep(base, mask, true_phase, rho)
    true_plane = angular_spectrum(base, -Z_TRUE)
    print(f"T1 focus: aperture-contrast peak "
          f"{result['contrast_peak_mm']:.3f} mm "
          f"(value {result['contrast_peak_value']:.4f}), "
          f"error {result['contrast_peak_mm'] - Z_TRUE * 1e3:+.3f} mm; "
          f"contrast at true plane "
          f"{aperture_contrast(true_plane, mask):.4f} "
          f"(peak only "
          f"{result['contrast_peak_value'] - aperture_contrast(true_plane, mask):.4f} "
          f"above it: the peak is flat-topped, focus located to ~±0.25 mm)")
    rms, agr = wavefront_at(base, result['contrast_peak_mm'] * 1e-3,
                            mask, true_phase, rho)
    emask = eroded_mask(rho, RADIUS, ERODE)
    rms_true = phase_rms_error(true_plane, true_phase, emask)
    print(f"T2 wavefront at measured focus (eroded mask, {ERODE} px): "
          f"RMS error {rms:.4f} waves, agreement {agr:.4f}; "
          f"at true plane RMS {rms_true:.4f} waves")
    base0, mask0, true0, rho0 = run_pipeline({})
    plane0 = angular_spectrum(base0, -Z_TRUE)
    emask0 = eroded_mask(rho0, RADIUS, ERODE)
    print(f"T3 null control (no aberrations, true plane): RMS error "
          f"{phase_rms_error(plane0, true0, emask0):.4f} waves")
    base_n, mask_n, true_n, rho_n = run_pipeline(ABERRATIONS,
                                                 hologram_noise=0.05)
    result_n = sweep(base_n, mask_n, true_n, rho_n)
    rms_n, agr_n = wavefront_at(base_n,
                                result_n['contrast_peak_mm'] * 1e-3,
                                mask_n, true_n, rho_n)
    print(f"T4 noise (5% of mean hologram): focus "
          f"{result_n['contrast_peak_mm']:.3f} mm "
          f"(error {result_n['contrast_peak_mm'] - Z_TRUE * 1e3:+.3f} mm), "
          f"wavefront RMS {rms_n:.4f} waves, agreement {agr_n:.4f}")
    print(f"T5 secondary (phase_variance minimum on the same sweep): "
          f"{result['phase_var_min_mm']:.3f} mm "
          f"(value {result['phase_var_min_value']:.4f}) vs "
          f"aperture-contrast peak {result['contrast_peak_mm']:.3f} mm")


if __name__ == "__main__":
    main()
