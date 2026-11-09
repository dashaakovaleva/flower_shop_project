"""Обучает модель на 2 годах и проверяет на отложенном 3-м году."""

from django.core.management.base import BaseCommand

from shop.forecasting.service import run_backtest


class Command(BaseCommand):
    help = "Запускает бэктест прогнозной модели (2 года обучения → 3-й год теста)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            default="sarimax",
            choices=["sarimax", "regression", "auto"],
            help="Прогнозная модель",
        )

    def handle(self, *args, **options):
        self.stdout.write("Обучение модели… Это может занять до нескольких минут.")
        run = run_backtest(model_name=options["model"])
        summary = run.summary or {}
        self.stdout.write(self.style.SUCCESS(f"Запуск #{run.pk} завершён."))
        self.stdout.write(f"Модель: {run.model_name}")
        self.stdout.write(
            f"Период: обучение {run.train_start}–{run.train_end}, "
            f"тест {run.test_start}–{run.test_end}"
        )
        for metric in run.metrics.all():
            self.stdout.write(
                f"  {metric.get_segment_display():12s} "
                f"MAE={metric.mae:8.2f}  RMSE={metric.rmse:8.2f}  "
                f"MAPE={metric.mape:6.2f}%  WAPE={metric.wape:6.2f}%  "
                f"bias={metric.bias_pct:6.2f}%  coverage={metric.coverage_pct:5.1f}%"
            )
        demand = summary.get("demand_confusion", {})
        stockout = summary.get("stockout_confusion", {})
        self.stdout.write(
            "Ошибки I/II рода (высокий спрос): "
            f"FP={demand.get('type_i_error', 0)}, FN={demand.get('type_ii_error', 0)}, "
            f"precision={demand.get('precision', 0)}%, recall={demand.get('recall', 0)}%"
        )
        self.stdout.write(
            "Ошибки I/II рода (дефицит на 7 дней): "
            f"FP={stockout.get('type_i_error', 0)}, FN={stockout.get('type_ii_error', 0)}, "
            f"precision={stockout.get('precision', 0)}%, recall={stockout.get('recall', 0)}%"
        )
        comparison = summary.get("comparison", {})
        if comparison.get("available"):
            self.stdout.write(
                "Синтетика vs реальные данные: "
                f"KS={comparison.get('ks_statistic')}, "
                f"r(неделя)={comparison.get('weekly_correlation')}, "
                f"r(месяц)={comparison.get('monthly_correlation')}"
            )
        self.stdout.write(f"Длительность: {summary.get('duration_seconds')} с.")
