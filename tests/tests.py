# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for waveholo-telescope. Run from the package root: python3 tests/tests.py.

Pins are set BELOW measured performance with margin, never at the
measured value: the demo reports the measured bars, the tests guard
against regressions. Grid 128 here for speed; the demo runs 256.
"""

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from waveholo_telescope.hologram import (  # noqa: E402
    record_hologram, reconstruct_field)
from waveholo_telescope.analysis import parabolic_peak  # noqa: E402
from waveholo_telescope.metrics import (  # noqa: E402
    aperture_contrast, eroded_mask, phase_agreement, phase_rms_error)
from waveholo_telescope.propagation import (  # noqa: E402
    DX, WL, TRANSFER_CACHE_MAXSIZE, _transfer, _transfer_cache, angular_spectrum)
from waveholo_telescope.pupil import (  # noqa: E402
    pupil_field, pupil_grid, zernike_phase)

N = 128
RADIUS = 32
Z_TRUE = 5.0e-3
ABERRATIONS = {"defocus": 0.4, "astig_x": 0.3, "coma_x": 0.2}


def _pipeline(aberrations):
    field, mask, true_phase = pupil_field(N, RADIUS, **aberrations)
    sensor = angular_spectrum(field, Z_TRUE)
    base = reconstruct_field(record_hologram(sensor, car=40), car=40, win=24)
    rho, _, _ = pupil_grid(N, RADIUS)
    return base, mask, true_phase, rho


class TestPupil(unittest.TestCase):
    def test_mask_area(self):
        _, _, mask = pupil_grid(N, RADIUS)
        area = int(mask.sum())
        expected = np.pi * RADIUS ** 2
        self.assertLess(abs(area - expected) / expected, 0.03)

    def test_field_zero_outside_mask(self):
        field, mask, _ = pupil_field(N, RADIUS, **ABERRATIONS)
        self.assertTrue(np.all(field[~mask] == 0))
        self.assertTrue(np.allclose(np.abs(field[mask]), 1.0))

    def test_zernike_pointwise(self):
        one = np.array([1.0])
        zero = np.array([0.0])
        self.assertAlmostEqual(
            zernike_phase(zero, zero, defocus=1.0)[0], -1.0)
        self.assertAlmostEqual(
            zernike_phase(one, zero, defocus=1.0)[0], 1.0)
        self.assertAlmostEqual(
            zernike_phase(one, zero, astig_x=1.0)[0], 1.0)
        self.assertAlmostEqual(
            zernike_phase(one, np.array([np.pi / 2]), astig_x=1.0)[0],
            -1.0)
        self.assertAlmostEqual(
            zernike_phase(one, zero, coma_x=1.0)[0], 1.0)
        self.assertAlmostEqual(
            zernike_phase(zero, zero, coma_x=1.0)[0], 0.0)

    def test_zernike_zero_mean_over_disk(self):
        rho, theta, mask = pupil_grid(N, RADIUS)
        for kwargs in ({"defocus": 1.0}, {"astig_x": 1.0},
                       {"coma_x": 1.0}):
            mean = float(zernike_phase(rho, theta, **kwargs)[mask].mean())
            self.assertLess(abs(mean), 0.02)

    def test_eroded_mask(self):
        rho, _, mask = pupil_grid(N, RADIUS)
        eroded = eroded_mask(rho, RADIUS, 2)
        self.assertTrue(np.all(eroded <= mask))
        self.assertLess(int(eroded.sum()), int(mask.sum()))
        self.assertTrue(np.array_equal(eroded_mask(rho, RADIUS, 0), mask))


class TestPropagation(unittest.TestCase):
    def test_roundtrip(self):
        rng = np.random.default_rng(7)
        field = rng.normal(size=(N, N)) + 1j * rng.normal(size=(N, N))
        back = angular_spectrum(angular_spectrum(field, Z_TRUE), -Z_TRUE)
        self.assertLess(np.max(np.abs(back - field)), 1e-9)

    def test_preserves_energy(self):
        rng = np.random.default_rng(7)
        field = rng.normal(size=(N, N)) + 1j * rng.normal(size=(N, N))
        moved = angular_spectrum(field, Z_TRUE)
        before = float(np.sum(np.abs(field) ** 2))
        after = float(np.sum(np.abs(moved) ** 2))
        self.assertLess(abs(after - before) / before, 1e-9)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            angular_spectrum(np.zeros((N, N + 1)), Z_TRUE)
        with self.assertRaises(ValueError):
            record_hologram(np.zeros((N, N), dtype=complex), car=0)
        with self.assertRaises(ValueError):
            record_hologram(np.zeros((N, N), dtype=complex), car=N // 2)
        with self.assertRaises(ValueError):
            record_hologram(np.zeros((N, N + 1), dtype=complex), car=40)
        with self.assertRaises(ValueError):
            angular_spectrum(np.zeros((N, N), dtype=complex), Z_TRUE, dx=0)
        with self.assertRaises(ValueError):
            reconstruct_field(np.zeros((N, N)), car=40.5, win=24)

    def test_transfer_cache_is_bounded(self):
        previous = dict(_transfer_cache)
        try:
            _transfer_cache.clear()
            for index in range(TRANSFER_CACHE_MAXSIZE + 1):
                _transfer(float(index), 64, DX, WL)
            self.assertEqual(len(_transfer_cache), TRANSFER_CACHE_MAXSIZE)
            self.assertNotIn((0.0, 64, DX, WL), _transfer_cache)
        finally:
            _transfer_cache.clear()
            _transfer_cache.update(previous)


class TestPipeline(unittest.TestCase):
    def test_hologram_nonnegative_and_mean(self):
        field, _, _ = pupil_field(N, RADIUS, **ABERRATIONS)
        sensor = angular_spectrum(field, Z_TRUE)
        holo = record_hologram(sensor, car=40)
        self.assertTrue(np.all(holo >= 0))
        expected = 1.0 + float(np.mean(np.abs(sensor) ** 2))
        self.assertLess(abs(float(holo.mean()) - expected), 0.05)

    def test_sideband_reconstruction_fidelity(self):
        field, _, _ = pupil_field(N, RADIUS, **ABERRATIONS)
        sensor = angular_spectrum(field, Z_TRUE)
        rec = reconstruct_field(record_hologram(sensor, car=40), car=40, win=24)
        num = abs(np.sum(np.conj(sensor) * rec))
        den = float(np.sqrt(np.sum(np.abs(sensor) ** 2)
                            * np.sum(np.abs(rec) ** 2)))
        self.assertGreater(num / den, 0.95)

    def test_contrast_peaks_near_true_plane(self):
        base, mask, _, _ = _pipeline(ABERRATIONS)
        c_true = aperture_contrast(angular_spectrum(base, -Z_TRUE), mask)
        c_near = aperture_contrast(angular_spectrum(base, -Z_TRUE + 1e-3),
                                   mask)
        c_far = aperture_contrast(angular_spectrum(base, -Z_TRUE - 1e-3),
                                  mask)
        self.assertGreater(c_true, c_near)
        self.assertGreater(c_true, c_far)

    def test_wavefront_recovery(self):
        base, mask, true_phase, rho = _pipeline(ABERRATIONS)
        plane = angular_spectrum(base, -Z_TRUE)
        emask = eroded_mask(rho, RADIUS, 2)
        self.assertLess(phase_rms_error(plane, true_phase, emask), 0.03)
        self.assertGreater(phase_agreement(plane, true_phase, emask), 0.98)

    def test_wrapped_rms_is_invariant_to_global_piston(self):
        _, mask, true_phase = pupil_field(N, RADIUS, defocus=0.49)
        field = np.zeros((N, N), dtype=complex)
        field[mask] = np.exp(2j * np.pi * true_phase[mask])
        piston_shifted = np.exp(1.37j) * field
        self.assertLess(phase_rms_error(piston_shifted, true_phase, mask), 1e-12)
        self.assertGreater(phase_agreement(piston_shifted, true_phase, mask), 1 - 1e-12)

    def test_wrapped_rms_keeps_separate_piston_definition(self):
        recovered = np.array([0.49, -0.49, 0.0])
        truth = np.array([0.1, 0.2, -0.3])
        field = np.exp(2j * np.pi * recovered)[None, :]
        mask = np.ones(field.shape, dtype=bool)
        separate_piston_rms = phase_rms_error(field, truth[None, :], mask)
        relative = (recovered - truth + 0.5) % 1.0 - 0.5
        relative_piston = np.angle(np.exp(2j * np.pi * relative).mean()) / (2 * np.pi)
        relative_aligned_rms = np.sqrt(
            np.mean(((relative - relative_piston + 0.5) % 1.0 - 0.5) ** 2)
        )
        self.assertAlmostEqual(separate_piston_rms, 0.0778888096369862)
        self.assertAlmostEqual(relative_aligned_rms, 0.040277915813968355)
        self.assertNotAlmostEqual(separate_piston_rms, relative_aligned_rms)

    def test_null_control(self):
        base, mask, true_phase, rho = _pipeline({})
        plane = angular_spectrum(base, -Z_TRUE)
        emask = eroded_mask(rho, RADIUS, 2)
        self.assertLess(phase_rms_error(plane, true_phase, emask), 0.03)

    def test_parabolic_peak_refinement_and_boundary_flag(self):
        distances = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        scores = -(distances - 2.25) ** 2
        result = parabolic_peak(distances, scores)
        self.assertAlmostEqual(result["refined_distance_m"], 2.25)
        self.assertFalse(result["at_boundary"])
        edge = parabolic_peak(distances, np.array([1., 0., 0., 0., 0.]))
        self.assertTrue(edge["at_boundary"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
