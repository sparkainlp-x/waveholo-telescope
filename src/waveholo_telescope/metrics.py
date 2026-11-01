"""Focus and wavefront metrics for the telescope pupil.

aperture_contrast (PRIMARY focus metric, MAXIMAL at focus):
at the true pupil plane the field amplitude is the aperture mask
itself -- 1 inside the disk, 0 outside. Defocus blurs the disk and
leaks energy outside it, so (mean |U|^2 inside - mean |U|^2
outside) / (mean |U|^2 inside + mean |U|^2 outside) peaks at the
pupil plane: 1 for a perfect disk, 0 when inside and outside carry
equal intensity. This is the metric WaveHolo's lab bench does not
need (its amplitude objects focus by the realness dip) and the
telescope pupil does: a pupil is a PHASE object, and the realness
dip does not apply to it -- the demo reports WaveHolo's
phase_variance alongside, as a secondary readout, so the
difference is measured, not asserted.

phase_rms_error (wavefront bar, in WAVES): at a candidate plane,
the recovered phase inside an eroded aperture mask, piston-removed
(circular mean phasor), compared against the injected aberration
phase, with differences wrapped to (-pi, pi]. The mask is eroded
by `erode` pixels because the hard aperture edge is blurred by
the sideband window, so rim pixels carry reconstruction error
that is not wavefront error. Erosion is stated wherever the bar
is reported. Erosion here is exact: the mask is rho <= 1, so
eroding by k pixels is rho <= 1 - k / radius.

phase_agreement: circular agreement of recovered vs injected
phase, |mean phasor of the wrapped difference| in [0, 1]; 1 is
perfect, 0 is random. This replaces a plain Pearson correlation,
which is WRONG on wrapped phases: where the true phase crosses
the +-0.5 wave seam, a tiny piston shift flips values from +0.5
to -0.5, and Pearson counts that seam as anti-correlation even
when the wrapped difference is tiny (measured on the first demo
run: RMS error 0.0066 waves alongside a Pearson 0.9529 -- the
0.9529 was the seam artifact, not wavefront error, so it is not
reported as a result anywhere).

phase_variance (WaveHolo's candidate universal metric, secondary
readout): intensity-weighted circular variance of the phase, 1 -
|mean phasor|; ~0 where the phase is uniform, -> 1 where it
scrambles. Reported on the same sweep so its peak can be compared
against the aperture-contrast peak on telescope data.
"""

from __future__ import annotations

import numpy as np


def aperture_contrast(field, mask):
    """(mean |U|^2 inside - mean |U|^2 outside) / (inside + outside)."""
    inten = np.abs(np.asarray(field, dtype=complex)) ** 2
    mask = np.asarray(mask, dtype=bool)
    if inten.shape != mask.shape or not mask.any() or mask.all():
        raise ValueError("field and mask must match and mask must have inside and outside pixels")
    inside = float(inten[mask].mean())
    outside = float(inten[~mask].mean())
    denom = inside + outside
    if denom <= 0 or not np.isfinite(denom):
        return 0.0
    return (inside - outside) / denom


def eroded_mask(rho, radius, erode):
    """Mask eroded by `erode` pixels: rho <= 1 - erode / radius."""
    if not np.isfinite(radius) or radius <= 0 or not np.isfinite(erode) or erode < 0:
        raise ValueError("radius must be positive and erode must be non-negative")
    if erode <= 0:
        return rho <= 1.0
    return rho <= 1.0 - erode / radius


def _piston_removed_phase(field, mask):
    """Phase in waves, piston-removed, inside mask (NaN outside)."""
    field = np.asarray(field, dtype=complex)
    mask = np.asarray(mask, dtype=bool)
    if field.shape != mask.shape or not mask.any():
        raise ValueError("field and mask must match and mask must be non-empty")
    phase = np.angle(field) / (2 * np.pi)
    phasor = np.exp(2j * np.pi * phase[mask])
    piston = np.angle(phasor.mean()) / (2 * np.pi)
    out = np.full(field.shape, np.nan)
    out[mask] = (phase[mask] - piston + 0.5) % 1.0 - 0.5
    return out


def phase_rms_error(field, true_phase_waves, mask):
    """RMS wrapped phase difference in waves, inside mask."""
    diff = _wrapped_diff(field, true_phase_waves, mask)
    return float(np.sqrt(np.mean(diff ** 2)))


def _wrapped_diff(field, true_phase_waves, mask):
    """Wrapped recovered-minus-true phase difference, in waves."""
    true_phase_waves = np.asarray(true_phase_waves, dtype=float)
    mask = np.asarray(mask, dtype=bool)
    if true_phase_waves.shape != mask.shape:
        raise ValueError("true_phase_waves and mask must have matching shapes")
    recovered = _piston_removed_phase(field, mask)
    true = np.full(field.shape, np.nan)
    true_piston = np.angle(
        np.exp(2j * np.pi * true_phase_waves[mask]).mean()) / (2 * np.pi)
    true[mask] = (true_phase_waves[mask] - true_piston + 0.5) % 1.0 - 0.5
    return (recovered[mask] - true[mask] + 0.5) % 1.0 - 0.5


def phase_agreement(field, true_phase_waves, mask):
    """|mean phasor of the wrapped phase difference|, in [0, 1]."""
    diff = _wrapped_diff(field, true_phase_waves, mask)
    return float(abs(np.exp(2j * np.pi * diff).mean()))


def phase_variance(field):
    """Intensity-weighted circular variance of the phase (WaveHolo's)."""
    field = np.asarray(field, dtype=complex)
    w = np.abs(field) ** 2
    total = float(w.sum())
    if total <= 0 or not np.isfinite(total):
        return 1.0
    mean_phasor = np.sum(w * np.exp(1j * np.angle(field))) / total
    return float(1.0 - abs(mean_phasor))
