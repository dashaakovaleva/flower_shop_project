"""Строит рабочий прогноз на 7 дней и рекомендации по закупке."""

from django.core.management.base import BaseCommand

from shop.forecasting.service import run_operational_forecast


class Command(BaseCommand):
    help = "Строит оперативный прогноз спроса и рекомендации по дозакупке"

    def add_arguments(self, parser):
        parser.add_argument("--horizon", type=int, default=7)
        parser.add_argument(
            "--model",
            default="sarimax",
            choices=["sarimax", "regression", "auto"],
        )

    def handle(self, *args, **options):
        self.stdout.write("Построение оперативного прогноза…")
        run = run_operational_forecast(
            horizon=options["horizon"], model_name=options["model"]
        )
        summary = run.summary or {}
        self.stdout.write(
            self.style.SUCCESS(
                f"Прогноз #{run.pk} на {run.horizon_days} дней готов. "
                f"Точек: {summary.get('forecast_points')}, "
                f"рекомендаций: {summary.get('recommendations')} "
                f"(критичных: {summary.get('critical')})."
            )
        )
        for recommendation in run.recommendations.select_related("product").order_by(
            "priority", "-purchase_quantity"
        )[:10]:
            self.stdout.write(
                f"  [{recommendation.get_priority_display():9s}] "
                f"{recommendation.product.name}: закупить "
                f"{recommendation.purchase_quantity} шт. "
                f"(остаток {recommendation.current_stock}, "
                f"прогноз {recommendation.forecast_demand:.0f})"
            )
