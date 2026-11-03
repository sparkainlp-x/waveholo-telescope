import unittest

import numpy as np

from waveholo_telescope.hologram import record_hologram, reconstruct_field
from waveholo_telescope.propagation import angular_spectrum
from waveholo_telescope.pupil import pupil_field


class SmallPipelineIntegrationTests(unittest.TestCase):
    def test_seeded_pupil_hologram_reconstruction_has_finite_shape(self):
        pupil, mask, _ = pupil_field(64, 16, defocus=0.1)
        sensor = angular_spectrum(pupil, 5e-3)
        hologram = record_hologram(sensor, car=20)
        recovered = reconstruct_field(hologram, car=20, win=12)
        self.assertEqual(hologram.shape, (64, 64))
        self.assertEqual(hologram.dtype.kind, "f")
        self.assertTrue(mask.any())
        self.assertTrue(np.isfinite(recovered).all())


if __name__ == "__main__":
    unittest.main()
