# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only

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
    if (d.ndim != 1 or d.size == 0 or not np.isfinite(d).all()
            or (d < 0).any() or (d.size > 1 and not np.all(np.diff(d) > 0))):
        raise ValueError("distances must be finite, non-negative, and strictly increasing")
    if (base.ndim != 2 or mask.ndim != 2 or base.shape != mask.shape
            or not mask.any() or mask.all()):
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
    Local quadratic fitting works on regular or irregular strictly increasing
    grids. Refinement is applied only when the maximum is interior, the
    parabola is concave, and its vertex lies between neighbouring samples.
    Plateau and weak-curvature flags describe sampling diagnostics, not
    confidence intervals.
    """
    d = np.asarray(distances, dtype=float)
    s = np.asarray(scores, dtype=float)
    if d.ndim != 1 or s.ndim != 1 or s.shape != d.shape or d.size < 1:
        raise ValueError("distances and scores must be matching non-empty 1-D arrays")
    if not np.isfinite(d).all() or not np.isfinite(s).all():
        raise ValueError("distances and scores must be finite")
    if d.size > 1 and not np.all(np.diff(d) > 0):
        raise ValueError("distances must be strictly increasing with no duplicates")
    i = int(np.argmax(s))
    refined = float(d[i])
    curvature = None
    refinement_applied = False
    if 0 < i < d.size - 1:
        offsets = d[i - 1:i + 2] - d[i]
        quadratic, linear, _ = np.linalg.solve(
            np.column_stack((offsets**2, offsets, np.ones(3))), s[i - 1:i + 2]
        )
        curvature = float(2 * quadratic)
        vertex = -linear / (2 * quadratic) if quadratic != 0 else np.nan
        if quadratic < 0 and d[i - 1] - d[i] <= vertex <= d[i + 1] - d[i]:
            refined += float(vertex)
            refinement_applied = True
    peak_tolerance = max(1e-12, 1e-12 * float(np.max(np.abs(s))))
    plateau = bool(np.count_nonzero(np.abs(s - s[i]) <= peak_tolerance) > 1)
    if d.size > 1:
        step = float(np.min(np.diff(d)))
        curvature_floor = 1e-6 * max(float(np.ptp(s)), np.finfo(float).eps) / step**2
        weak_curvature = curvature is None or abs(curvature) <= curvature_floor
        resolution = 0.5 * step
    else:
        weak_curvature = True
        resolution = None
    return {
        "sampled_distance_m": float(d[i]),
        "refined_distance_m": refined,
        "score": float(s[i]),
        "curvature_per_m2": curvature,
        "resolution_half_step_m": resolution,
        "at_boundary": bool(i == 0 or i == d.size - 1),
        "plateau": plateau,
        "weak_curvature": bool(weak_curvature),
        "refinement_applied": refinement_applied,
    }
