"""Angular-spectrum propagation, the same kernel as waveholo v0.1.5.

Bench parameters are WaveHolo's own, kept deliberately so this
telescope adaptation is comparable to the lab bench, not a new
instrument: wavelength 532 nm, pixel pitch 6.5 um, grid 256x256,
off-axis carrier 80 bins, sideband half-width 48 bins.

Kernel: U_z = IFFT(FFT(U) * exp(i k z sqrt(1 - (wl fx)^2 - (wl fy)^2))),
with evanescent components (argument <= 0) dropped -- they carry no
energy to the sensor. Negative z back-propagates. The transfer
function has unit modulus wherever it is nonzero, so propagation is
energy-preserving up to the evanescent cutoff.
"""

from __future__ import annotations

import numpy as np

N = 256
DX = 6.5e-6
WL = 532e-9
CAR_DEFAULT = 80
WIN_DEFAULT = 48

_transfer_cache = {}


def _transfer(z, n, dx, wl):
    if not isinstance(n, (int, np.integer)) or n <= 0:
        raise ValueError("n must be a positive integer")
    if not np.isfinite(dx) or dx <= 0:
        raise ValueError("dx must be a positive finite number of metres")
    if not np.isfinite(wl) or wl <= 0:
        raise ValueError("wl must be a positive finite number of metres")
    key = (float(z), n, dx, wl)
    if key not in _transfer_cache:
        fx = np.fft.fftfreq(n, d=dx)
        FX, FY = np.meshgrid(fx, fx)
        k = 2 * np.pi / wl
        arg = 1.0 - (wl * FX) ** 2 - (wl * FY) ** 2
        _transfer_cache[key] = np.where(
            arg > 0, np.exp(1j * k * z * np.sqrt(np.maximum(arg, 0))), 0
        )
    return _transfer_cache[key]


def angular_spectrum(field, z, dx=DX, wl=WL):
    """Propagate a square 2D complex field by distance z (m)."""
    field = np.asarray(field, dtype=complex)
    if field.ndim != 2 or field.shape[0] != field.shape[1]:
        raise ValueError("field must be a square 2D array")
    if not np.isfinite(field).all() or not np.isfinite(z):
        raise ValueError("field and z must be finite")
    if not np.isfinite(dx) or dx <= 0:
        raise ValueError("dx must be a positive finite number of metres")
    if not np.isfinite(wl) or wl <= 0:
        raise ValueError("wl must be a positive finite number of metres")
    n = field.shape[0]
    return np.fft.ifft2(np.fft.fft2(field) * _transfer(z, n, dx, wl))
