import unittest

import numpy as np

from waveholo_telescope.benchmark import run_condition


class RepeatabilityProperties(unittest.TestCase):
    def test_fixed_seed_repeats_identically(self):
        left = run_condition(seed=91, n=64, radius=16, carrier=20, window=12, sweep_points=5)
        right = run_condition(seed=91, n=64, radius=16, carrier=20, window=12, sweep_points=5)
        left.pop("runtime_seconds")
        right.pop("runtime_seconds")
        self.assertEqual(left, right)

    def test_noise_is_reproducible_for_generator_seed(self):
        from waveholo_telescope.benchmark import _add_sensor_noise
        image = np.arange(16, dtype=float).reshape(4, 4)
        first = _add_sensor_noise(image, 0.1, np.random.default_rng(2))
        second = _add_sensor_noise(image, 0.1, np.random.default_rng(2))
        np.testing.assert_array_equal(first, second)


if __name__ == "__main__":
    unittest.main()
