import unittest

from waveholo_telescope.statistics import median_and_iqr


class SummarySchemaRegressionTests(unittest.TestCase):
    def test_distribution_summary_schema_is_stable(self):
        summary = median_and_iqr([1, 2, 3])
        self.assertEqual(
            set(summary),
            {"n", "median", "q1", "q3", "iqr", "min", "max"},
        )
        self.assertEqual(summary["median"], 2.0)


if __name__ == "__main__":
    unittest.main()
