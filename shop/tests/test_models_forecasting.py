from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
from django.test import SimpleTestCase, TestCase

from shop.forecasting.backends import SeasonalRegressionModel, fit_predict
from shop.models import Category, ModelMetric, ModelRun, Order, PeakDate, Product, Recommendation


class PeakDateTests(SimpleTestCase):
    def test_next_occurrence_rolls_to_next_year(self):
        peak = PeakDate(name="8 марта", month=3, day=8)
        self.assertEqual(peak.next_occurrence(date(2026, 1, 1)), date(2026, 3, 8))
        self.assertEqual(peak.next_occurrence(date(2026, 4, 1)), date(2027, 3, 8))

    def test_days_until(self):
        peak = PeakDate(name="14 февраля", month=2, day=14)
        self.assertEqual(peak.days_until(date(2026, 2, 10)), 4)


class ProductAndOrderPropertyTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Тест", slug="test")
        self.product = Product.objects.create(
            category=category,
            name="Тестовый цветок",
            sku="TEST-1",
            price=Decimal("200.00"),
            cost_price=Decimal("120.00"),
            stock_quantity=3,
            min_stock=5,
        )

    def test_stock_status_and_margin(self):
        self.assertEqual(self.product.stock_status, "low")
        self.assertEqual(self.product.margin, Decimal("80.00"))
        self.assertAlmostEqual(self.product.margin_percent, 40.0)
        self.product.stock_quantity = 0
        self.assertEqual(self.product.stock_status, "out")

    def test_model_metric_helpers(self):
        run = ModelRun.objects.create(kind=ModelRun.Kind.BACKTEST, model_name="test")
        ModelMetric.objects.create(run=run, segment=ModelMetric.Segment.ALL, mae=1.5)
        ModelMetric.objects.create(run=run, segment=ModelMetric.Segment.PEAK, mae=2.5)
        self.assertEqual(run.metric_all.mae, 1.5)
        self.assertEqual(run.metric_peak.mae, 2.5)
        self.assertIsNone(run.metric_normal)

    def test_order_number_and_cancel_flag(self):
        from shop.models import Customer

        customer = Customer.objects.create(full_name="Тест")
        order = Order.objects.create(customer=customer)
        self.assertEqual(order.number, f"FL-{order.pk:05d}")
        self.assertTrue(order.can_cancel)
        order.status = Order.Status.COMPLETED
        self.assertFalse(order.can_cancel)

    def test_recommendation_coverage(self):
        run = ModelRun.objects.create(kind=ModelRun.Kind.OPERATIONAL, model_name="test")
        rec = Recommendation(
            run=run,
            product=self.product,
            forecast_demand=20,
            current_stock=10,
            safety_stock=3,
            required_stock=23,
            purchase_quantity=13,
            priority=Recommendation.Priority.HIGH,
        )
        self.assertAlmostEqual(rec.coverage_percent, 43.478, places=2)
        self.assertEqual(rec.priority_label, "Высокий")


class BackendTests(SimpleTestCase):
    HOLIDAYS = [
        {
            "code": "test",
            "name": "Тест",
            "short_name": "Тест",
            "month": 3,
            "day": 8,
            "window": 7,
            "coefficient": 2.0,
            "color": "#000",
        }
    ]

    def test_regression_model_fit_predict(self):
        dates = pd.date_range("2025-01-01", periods=90)
        y = 10 + 5 * np.sin(np.arange(90) * 2 * np.pi / 7) + np.arange(90) * 0.05
        model = SeasonalRegressionModel().fit(dates, y, self.HOLIDAYS)
        prediction = model.predict(pd.date_range("2025-04-01", periods=7), self.HOLIDAYS)
        self.assertEqual(len(prediction.mean), 7)
        self.assertTrue(np.isfinite(prediction.mean).all())
        self.assertTrue((prediction.lower <= prediction.mean).all())
        self.assertTrue((prediction.upper >= prediction.mean).all())

    def test_fit_predict_uses_regression_backend(self):
        dates = pd.date_range("2025-01-01", periods=60)
        y = np.linspace(10, 15, 60)
        prediction = fit_predict(
            dates,
            y,
            pd.date_range("2025-03-02", periods=7),
            self.HOLIDAYS,
            model_name="regression",
        )
        self.assertEqual(len(prediction.mean), 7)
        self.assertFalse(prediction.fallback)
