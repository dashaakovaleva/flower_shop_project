import numpy as np
import pandas as pd
from django.test import SimpleTestCase

from shop.forecasting.metrics import (
    comparison_stats,
    high_demand_confusion,
    regression_metrics,
    weekly_stockout_confusion,
)


class RegressionMetricsTests(SimpleTestCase):
    def test_perfect_forecast(self):
        metrics = regression_metrics([10, 20, 30], [10, 20, 30])
        self.assertEqual(metrics["mae"], 0)
        self.assertEqual(metrics["rmse"], 0)
        self.assertEqual(metrics["mape"], 0)
        self.assertEqual(metrics["wape"], 0)

    def test_known_error_values(self):
        # Ошибки: +2, -2, +2 → MAE=2, RMSE=2,
        # MAPE=(2/10+2/20+2/30)/3*100 ≈ 12.22, WAPE=6/60*100=10
        metrics = regression_metrics([10, 20, 30], [12, 18, 32], [0, 0, 0], [100, 100, 100])
        self.assertAlmostEqual(metrics["mae"], 2.0, places=3)
        self.assertAlmostEqual(metrics["rmse"], 2.0, places=3)
        self.assertAlmostEqual(metrics["mape"], 12.222, places=2)
        self.assertAlmostEqual(metrics["wape"], 10.0, places=2)
        self.assertAlmostEqual(metrics["bias_pct"], 3.333, places=2)
        self.assertAlmostEqual(metrics["coverage_pct"], 100.0, places=2)

    def test_empty_input(self):
        metrics = regression_metrics([], [])
        self.assertEqual(metrics["n_obs"], 0)


class ConfusionTests(SimpleTestCase):
    def test_high_demand_confusion_per_product(self):
        train = pd.DataFrame(
            {
                "product_id": [1] * 10 + [2] * 10,
                "quantity": list(range(1, 11)) + list(range(10, 20)),
            }
        )
        frame = pd.DataFrame(
            {
                "product_id": [1, 1, 1, 2, 2],
                "actual": [10, 1, 1, 20, 10],
                "predicted": [3, 2, 9, 19, 10],
            }
        )
        result = high_demand_confusion(frame, train)
        self.assertEqual(result["tp"], 1)
        self.assertEqual(result["fp"], 1)
        self.assertEqual(result["fn"], 1)
        self.assertEqual(result["tn"], 2)
        self.assertEqual(result["type_i_error"], 1)
        self.assertEqual(result["type_ii_error"], 1)

    def test_stockout_confusion_counts_all_windows(self):
        train = pd.DataFrame(
            {
                "product_id": [1] * 28,
                "date": pd.date_range("2025-01-01", periods=28),
                "quantity": [5] * 28,
            }
        )
        frame = pd.DataFrame(
            {
                "product_id": [1] * 7,
                "date": pd.date_range("2025-02-01", periods=7),
                "actual": [5] * 7,
                "predicted": [5] * 7,
            }
        )
        result = weekly_stockout_confusion(frame, train)
        self.assertEqual(result["total"], 1)
        self.assertEqual(
            result["tp"] + result["fp"] + result["fn"] + result["tn"], 1
        )


class ComparisonTests(SimpleTestCase):
    def test_comparison_returns_profiles_and_statistics(self):
        synthetic = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=28),
                "quantity": np.tile([10, 11, 12, 13, 14, 20, 18], 4),
            }
        )
        real = pd.DataFrame(
            {
                "date": pd.date_range("2019-01-07", periods=28),
                "quantity": np.tile([9, 10, 11, 12, 13, 19, 17], 4),
            }
        )
        stats = comparison_stats(synthetic, real)
        self.assertTrue(stats["available"])
        self.assertEqual(len(stats["weekly_synthetic"]), 7)
        self.assertEqual(len(stats["monthly_synthetic"]), 1)
        self.assertGreater(stats["weekly_correlation"], 0.9)
        self.assertIn("ks_pvalue", stats)

    def test_comparison_handles_empty_frames(self):
        stats = comparison_stats(pd.DataFrame(), pd.DataFrame())
        self.assertFalse(stats["available"])
