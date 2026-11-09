"""Экспортирует метрики последних запусков в JSON и CSV для отчёта."""

import csv
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from shop.models import ModelMetric, ModelRun


class Command(BaseCommand):
    help = "Сохраняет метрики бэктеста и оперативного прогноза в docs/"

    def handle(self, *args, **options):
        docs_dir = Path(settings.BASE_DIR) / "docs"
        docs_dir.mkdir(exist_ok=True)

        backtest = (
            ModelRun.objects.filter(
                kind=ModelRun.Kind.BACKTEST, status=ModelRun.Status.COMPLETED
            )
            .order_by("-created_at")
            .first()
        )
        operational = (
            ModelRun.objects.filter(
                kind=ModelRun.Kind.OPERATIONAL, status=ModelRun.Status.COMPLETED
            )
            .order_by("-created_at")
            .first()
        )

        payload = {
            "backtest": {
                "id": backtest.id if backtest else None,
                "model": backtest.model_name if backtest else None,
                "train": [str(backtest.train_start), str(backtest.train_end)] if backtest else None,
                "test": [str(backtest.test_start), str(backtest.test_end)] if backtest else None,
                "summary": backtest.summary if backtest else None,
                "metrics": [
                    {
                        "segment": metric.segment,
                        "n_obs": metric.n_obs,
                        "mae": metric.mae,
                        "rmse": metric.rmse,
                        "mape": metric.mape,
                        "wape": metric.wape,
                        "bias_pct": metric.bias_pct,
                        "coverage_pct": metric.coverage_pct,
                    }
                    for metric in (backtest.metrics.all() if backtest else [])
                ],
            },
            "operational": {
                "id": operational.id if operational else None,
                "summary": operational.summary if operational else None,
                "recommendations": [
                    {
                        "product": recommendation.product.name,
                        "priority": recommendation.priority,
                        "forecast_demand": recommendation.forecast_demand,
                        "current_stock": recommendation.current_stock,
                        "purchase_quantity": recommendation.purchase_quantity,
                    }
                    for recommendation in (
                        operational.recommendations.select_related("product")
                        if operational
                        else []
                    )
                ],
            },
        }

        json_path = docs_dir / "metrics.json"
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        csv_path = docs_dir / "metrics.csv"
        metrics_qs = (
            ModelMetric.objects.filter(run=backtest)
            if backtest
            else ModelMetric.objects.none()
        )
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(
                ["run_id", "segment", "n_obs", "mae", "rmse", "mape", "wape", "bias_pct", "coverage_pct"]
            )
            for metric in metrics_qs:
                writer.writerow(
                    [
                        metric.run_id,
                        metric.segment,
                        metric.n_obs,
                        metric.mae,
                        metric.rmse,
                        metric.mape,
                        metric.wape,
                        metric.bias_pct,
                        metric.coverage_pct,
                    ]
                )

        self.stdout.write(
            self.style.SUCCESS(f"Метрики сохранены: {json_path} и {csv_path}")
        )
