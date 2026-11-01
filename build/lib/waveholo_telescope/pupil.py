"""Telescope pupil: a circular aperture with Zernike aberrations.

The pupil field is P = A * exp(i phi), where A is 1 inside a disk
of radius R pixels and 0 outside, and phi is a sum of Zernike
phase terms with coefficients in WAVES (1 wave = 2 pi radians):

- defocus:  2 rho^2 - 1            (Z4; -1 at centre, +1 at rim)
- astig_x:  rho^2 cos(2 theta)     (Z5)
- astig_y:  rho^2 sin(2 theta)     (Z6)
- coma_x:   (3 rho^3 - 2 rho) cos(theta)  (Z7)
- coma_y:   (3 rho^3 - 2 rho) sin(theta)  (Z8)

rho is the normalized pupil radius (0 at centre, 1 at rim), theta
the azimuth. Outside the disk the field is exactly zero.

Deliberate exclusions, stated, not hidden:
- Piston is unobservable in a hologram (a global phase offset
  vanishes in |U + R|^2 up to the reference), so no piston term.
- Tip/tilt are pointing, not wavefront shape, and a tilt of the
  pupil field is absorbed by the sideband centering; they are
  excluded from the aberration budget here.
- No spider vanes, no central obstruction, no segmentation: a
  clean circular pupil, so the bars measure the pipeline, not a
  particular telescope's geometry.
"""

from __future__ import annotations

import numpy as np


def pupil_grid(n, radius):
    """(rho, theta, mask) on an n x n grid for a disk of radius pixels."""
    y, x = np.mgrid[0:n, 0:n]
    cx = cy = n // 2
    dx = (x - cx) / radius
    dy = (y - cy) / radius
    rho = np.hypot(dx, dy)
    theta = np.arctan2(dy, dx)
    mask = rho <= 1.0
    return rho, theta, mask


def zernike_phase(rho, theta, defocus=0.0, astig_x=0.0, astig_y=0.0,
                  coma_x=0.0, coma_y=0.0):
    """Aberration phase in WAVES (not radians) at each grid point."""
    phi = (defocus * (2 * rho ** 2 - 1)
           + astig_x * (rho ** 2 * np.cos(2 * theta))
           + astig_y * (rho ** 2 * np.sin(2 * theta))
           + coma_x * ((3 * rho ** 3 - 2 * rho) * np.cos(theta))
           + coma_y * ((3 * rho ** 3 - 2 * rho) * np.sin(theta)))
    return phi


def pupil_field(n, radius, **aberrations):
    """Complex pupil field plus (mask, true phase in waves).

    The true phase is returned for the ground-truth comparison: it
    is the injected aberration, in waves, valid inside the mask.
    """
    rho, theta, mask = pupil_grid(n, radius)
    phase_waves = zernike_phase(rho, theta, **aberrations)
    field = np.zeros((n, n), dtype=complex)
    field[mask] = np.exp(2j * np.pi * phase_waves[mask])
    return field, mask, phase_waves
