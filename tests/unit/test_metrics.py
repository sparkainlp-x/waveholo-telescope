import unittest

import numpy as np

from waveholo_telescope.metrics import aperture_contrast, phase_agreement, phase_rms_error


class MetricUnitTests(unittest.TestCase):
    def test_perfect_disk_has_unit_aperture_contrast(self):
        mask = np.array([[True, True], [False, False]])
        self.assertEqual(aperture_contrast(mask.astype(complex), mask), 1.0)

    def test_exact_wavefront_has_zero_rms_and_unit_agreement(self):
        phase = np.array([[0.0, 0.1], [0.2, 0.3]])
        mask = np.ones((2, 2), dtype=bool)
        field = np.exp(2j * np.pi * phase)
        self.assertAlmostEqual(phase_rms_error(field, phase, mask), 0.0, places=14)
        self.assertAlmostEqual(phase_agreement(field, phase, mask), 1.0, places=14)


if __name__ == "__main__":
    unittest.main()
