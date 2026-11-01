"""Reproducible focus analysis helpers for synthetic and camera data.

The focus score is deliberately aperture contrast, not phase uniformity: a
real telescope pupil can contain genuine phase structure at best focus.
Distances are physical metres and scores are returned with the input order
preserved. The curvature estimate is a local *sampling sensitivity* estimate,
not a confidence interval; repeat measurements are required for statistical
uncertainty.
"""
from __future__ import annotations

import numpy as np

from .metrics import aperture_contrast
from .propagation import angular_spectrum


def focus_sweep(base_field, pupil_mask, distances, *, dx=None, wl=None):
    """Evaluate aperture contrast after back-propagating to ``distances``.

    Parameters
    ----------
    base_field : 2-D complex ndarray
        Reconstructed sensor-plane field.
    pupil_mask : 2-D bool ndarray
        Expected pupil support in the reconstruction grid.
    distances : 1-D iterable of float
        Positive or zero sensor-to-pupil distances in metres.
    dx, wl : optional float
        Sampling pitch and wavelength passed to angular-spectrum propagation.

    Returns
    -------
    tuple of ndarray
        ``(distances, contrasts)`` as float arrays.
    """
    base = np.asarray(base_field, dtype=complex)
    mask = np.asarray(pupil_mask, dtype=bool)
    d = np.asarray(list(distances), dtype=float)
    if d.ndim != 1 or d.size == 0 or not np.isfinite(d).all() or (d < 0).any():
        raise ValueError("distances must be a non-empty 1-D array of finite non-negative metres")
    if base.shape != mask.shape:
        raise ValueError("base_field and pupil_mask must have matching shapes")
    kwargs = {}
    if dx is not None:
        kwargs["dx"] = dx
    if wl is not None:
        kwargs["wl"] = wl
    scores = np.empty(d.size, dtype=float)
    for i, distance in enumerate(d):
        scores[i] = aperture_contrast(
            angular_spectrum(base, -float(distance), **kwargs), mask
        )
    return d, scores


def parabolic_peak(distances, scores):
    """Return a quadratic refinement of the sampled maximum.

    The returned dictionary includes the sampled maximum, refined location,
    local curvature, and a conservative half-step resolution. Refinement is
    only applied when the maximum is interior and the parabola is concave.
    """
    d = np.asarray(distances, dtype=float)
    s = np.asarray(scores, dtype=float)
    if d.ndim != 1 or s.shape != d.shape or d.size < 1:
        raise ValueError("distances and scores must be matching non-empty 1-D arrays")
    if not np.isfinite(d).all() or not np.isfinite(s).all():
        raise ValueError("distances and scores must be finite")
    i = int(np.argmax(s))
    refined = float(d[i])
    curvature = np.nan
    if 0 < i < d.size - 1:
        step_left, step_right = d[i] - d[i - 1], d[i + 1] - d[i]
        if np.isclose(step_left, step_right) and step_left > 0:
            denom = s[i - 1] - 2.0 * s[i] + s[i + 1]
            curvature = float(denom / step_left**2)
            if denom < 0:
                refined += float(0.5 * (s[i - 1] - s[i + 1]) / denom * step_left)
    return {
        "sampled_distance_m": float(d[i]),
        "refined_distance_m": refined,
        "score": float(s[i]),
        "curvature_per_m2": curvature,
        "resolution_half_step_m": float(0.5 * np.min(np.diff(d))) if d.size > 1 else np.nan,
        "at_boundary": bool(i == 0 or i == d.size - 1),
    }
