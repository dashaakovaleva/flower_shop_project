from datetime import date

import numpy as np
import pandas as pd
from django.test import SimpleTestCase

from shop.forecasting.constants import PRODUCT_BLUEPRINTS
from shop.forecasting.features import holiday_feature_frame, holiday_name_for_date
from shop.forecasting.synthetic import daily_totals, generate_dataset, generate_train_and_holdout


class SyntheticGeneratorTests(SimpleTestCase):
    def test_generates_all_products_for_each_day(self):
        frame = generate_dataset(
            date(2025, 2, 1),
            date(2025, 2, 28),
            dataset="train",
            seed=1,
        )
        self.assertEqual(len(frame), 28 * len(PRODUCT_BLUEPRINTS))
        self.assertEqual(frame["date"].nunique(), 28)
        self.assertTrue((frame["quantity"] >= 0).all())
        self.assertTrue((frame["revenue"] >= 0).all())

    def test_peak_dates_have_higher_demand(self):
        frame = generate_dataset(
            date(2025, 2, 1),
            date(2025, 3, 15),
            dataset="train",
            seed=2,
        )
        march8 = frame[frame["date"] == pd.Timestamp("2025-03-08")]
        normal = frame[~frame["is_peak"]]
        self.assertTrue(march8["is_peak"].all())
        self.assertGreater(
            march8["quantity"].mean(),
            normal["quantity"].mean() * 1.3,
        )

    def test_train_and_holdout_periods_do_not_overlap(self):
        train, holdout, meta = generate_train_and_holdout(date(2026, 11, 9))
        self.assertEqual(len(train) + len(holdout), 3 * 365 * len(PRODUCT_BLUEPRINTS))
        self.assertLessEqual(train["date"].max(), holdout["date"].min() - pd.Timedelta(days=1))
        self.assertEqual(meta["train_rows"], len(train))
        self.assertEqual(meta["holdout_rows"], len(holdout))
        self.assertEqual(set(train["dataset"]), {"train"})
        self.assertEqual(set(holdout["dataset"]), {"holdout"})

    def test_daily_totals_without_revenue_column(self):
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02"]),
                "quantity": [1, 2, 3],
            }
        )
        totals = daily_totals(frame)
        self.assertEqual(list(totals.columns), ["date", "quantity"])
        self.assertEqual(totals["quantity"].tolist(), [3, 3])


class FeatureTests(SimpleTestCase):
    HOLIDAYS = [
        {
            "code": "test",
            "name": "Тестовый праздник",
            "short_name": "Тест",
            "month": 3,
            "day": 8,
            "window": 7,
            "coefficient": 2.0,
            "color": "#000",
        }
    ]

    def test_holiday_window_is_marked(self):
        frame = holiday_feature_frame(
            pd.DatetimeIndex(["2025-03-06", "2025-03-08", "2025-04-01"]),
            self.HOLIDAYS,
        )
        self.assertGreater(frame.loc["2025-03-06", "pre_test"], 0)
        self.assertEqual(frame.loc["2025-03-08", "day_test"], 1.0)
        self.assertEqual(frame.loc["2025-04-01", "pre_test"], 0.0)

    def test_trend_is_continuous_between_periods(self):
        train_dates = pd.DatetimeIndex(pd.date_range("2024-12-30", "2025-01-02"))
        test_dates = pd.DatetimeIndex(pd.date_range("2025-01-03", "2025-01-05"))
        train_frame = holiday_feature_frame(train_dates, self.HOLIDAYS)
        test_frame = holiday_feature_frame(test_dates, self.HOLIDAYS)
        self.assertLess(
            train_frame["trend"].iloc[-1],
            test_frame["trend"].iloc[0],
        )
        self.assertAlmostEqual(
            test_frame["trend"].iloc[0] - train_frame["trend"].iloc[-1],
            1 / 365.25,
            places=6,
        )

    def test_holiday_name_lookup(self):
        is_peak, name = holiday_name_for_date(date(2025, 3, 8), self.HOLIDAYS)
        self.assertTrue(is_peak)
        self.assertEqual(name, "Тест")
        is_peak, name = holiday_name_for_date(date(2025, 4, 1), self.HOLIDAYS)
        self.assertFalse(is_peak)
