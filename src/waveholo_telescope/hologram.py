"""Off-axis hologram recording and sideband reconstruction.

Same formulas as waveholo v0.1.5, unchanged: H = |U + R|^2 with a
reference tilted along x (carrier in FFT bins), then the object
sideband is cropped in Fourier space and shifted to baseband. The
crop window is clipped to the array if it touches an edge, so
missing bins stay zero rather than wrapping in from the opposite
side of the spectrum.
"""

from __future__ import annotations

import numpy as np

from .propagation import CAR_DEFAULT, WIN_DEFAULT


def record_hologram(sensor_field, car=CAR_DEFAULT):
    """Off-axis hologram intensity H = |U + R|^2."""
    field = np.asarray(sensor_field, dtype=complex)
    n = field.shape[0]
    if not (0 < car < n // 2):
        raise ValueError(f"carrier must satisfy 0 < car < {n // 2}")
    y, x = np.mgrid[0:n, 0:n]
    ref = np.exp(2j * np.pi * (car * x / n))
    return np.abs(field + ref) ** 2


def reconstruct_field(hologram, car=CAR_DEFAULT, win=WIN_DEFAULT):
    """Isolate the object sideband in Fourier space, shift to baseband."""
    holo = np.asarray(hologram, dtype=float)
    n = holo.shape[0]
    if not (0 < car < n) or not (0 <= win < n // 2):
        raise ValueError("need 0 < carrier < n and 0 <= window < n/2")
    spec = np.fft.fftshift(np.fft.fft2(holo))
    c = n // 2
    row_lo, row_hi = c - win, c + win
    col_lo, col_hi = c - car - win, c - car + win
    row_lo_c, row_hi_c = max(row_lo, 0), min(row_hi, n - 1)
    col_lo_c, col_hi_c = max(col_lo, 0), min(col_hi, n - 1)
    if row_lo_c > row_hi_c or col_lo_c > col_hi_c:
        raise ValueError("sideband window does not overlap the spectrum")
    crop = spec[row_lo_c:row_hi_c + 1, col_lo_c:col_hi_c + 1]
    full = np.zeros((n, n), dtype=complex)
    full[row_lo_c:row_hi_c + 1, col_lo_c + car:col_hi_c + car + 1] = crop
    return np.fft.ifft2(np.fft.ifftshift(full))


def offaxis_field(sensor_field, car=CAR_DEFAULT, win=WIN_DEFAULT):
    """Record an off-axis hologram and return the baseband field."""
    return reconstruct_field(record_hologram(sensor_field, car), car, win)
