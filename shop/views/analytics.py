import pandas as pd
from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from shop.forecasting.charts import (
    backtest_chart,
    demand_error_histogram,
    metrics_comparison_chart,
    monthly_comparison_chart,
    weekly_comparison_chart,
)
from shop.forecasting.metrics import comparison_stats, regression_metrics
from shop.forecasting.service import latest_run, run_backtest
from shop.forecasting.synthetic import daily_totals
from shop.models import ModelRun, RealMarketRecord, SalesRecord
from shop.permissions import role_required


def _forecast_frame(run: ModelRun) -> pd.DataFrame:
    rows = list(
        run.forecasts.values(
            "product_id",
            "product__name",
            "date",
            "predicted_quantity",
            "lower_bound",
            "upper_bound",
            "actual_quantity",
            "is_peak",
            "holiday_name",
        )
    )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.rename(
            columns={
                "predicted_quantity": "predicted",
                "lower_bound": "lower",
                "upper_bound": "upper",
                "actual_quantity": "actual",
                "product__name": "product_name",
            }
        )
        frame["date"] = pd.to_datetime(frame["date"])
    return frame


@require_GET
@role_required("manager", "admin")
def analytics_view(request):
    run_id = request.GET.get("run")
    backtest_runs = ModelRun.objects.filter(
        kind=ModelRun.Kind.BACKTEST, status=ModelRun.Status.COMPLETED
    ).order_by("-created_at")
    run = get_object_or_404(backtest_runs, pk=run_id) if run_id else backtest_runs.first()

    if not run:
        return render(
            request,
            "shop/analytics.html",
            {"run": None, "no_run": True, "backtest_runs": backtest_runs},
        )

    frame = _forecast_frame(run)
    metrics = list(run.metrics.all().order_by("segment"))
    metric_dicts = [
        {
            "segment": metric.segment,
            "mae": metric.mae,
            "rmse": metric.rmse,
            "mape": metric.mape,
            "wape": metric.wape,
            "bias_pct": metric.bias_pct,
            "coverage_pct": metric.coverage_pct,
            "n_obs": metric.n_obs,
            "actual_mean": metric.actual_mean,
            "predicted_mean": metric.predicted_mean,
        }
        for metric in metrics
    ]

    per_product = []
    if not frame.empty:
        for product_id, group in frame.groupby("product_id"):
            values = regression_metrics(group["actual"], group["predicted"], group["lower"], group["upper"])
            values["product_name"] = group["product_name"].iloc[0]
            values["product_id"] = int(product_id)
            peak_group = group[group["is_peak"].astype(bool)]
            if not peak_group.empty:
                values["peak_mape"] = regression_metrics(
                    peak_group["actual"], peak_group["predicted"]
                )["mape"]
            else:
                values["peak_mape"] = None
            per_product.append(values)
        per_product.sort(key=lambda item: item["mape"], reverse=True)

    summary = run.summary or {}
    context = {
        "run": run,
        "run_metrics": metrics,
        "metric_dicts": metric_dicts,
        "metric_all": next((m for m in metrics if m.segment == "all"), None),
        "metric_normal": next((m for m in metrics if m.segment == "normal"), None),
        "metric_peak": next((m for m in metrics if m.segment == "peak"), None),
        "per_product": per_product,
        "summary": summary,
        "demand_confusion": summary.get("demand_confusion", {}),
        "stockout_confusion": summary.get("stockout_confusion", {}),
        "comparison": summary.get("comparison", {}),
        "backtest_chart": backtest_chart(frame, "Суммарный факт и прогноз на отложенном году"),
        "error_chart": demand_error_histogram(frame),
        "metrics_chart": metrics_comparison_chart(metric_dicts),
        "backtest_runs": backtest_runs,
        "no_run": False,
    }
    return render(request, "shop/analytics.html", context)


@require_POST
@role_required("manager", "admin")
def backtest_run_view(request):
    try:
        run = run_backtest()
        messages.success(
            request,
            f"Бэктест завершён за {run.summary.get('duration_seconds', '—')} с. "
            f"MAPE: {run.metric('all').mape if run.metric('all') else '—'}%.",
        )
        return redirect(f"/analytics/?run={run.pk}")
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Ошибка обучения: {exc}")
        return redirect("analytics")


@require_GET
@role_required("manager", "admin")
def comparison_view(request):
    run = latest_run(ModelRun.Kind.BACKTEST)
    stats = (run.summary or {}).get("comparison", {}) if run else {}

    # Пересчитываем сравнение, чтобы страница работала даже без бэктеста.
    if not stats.get("available"):
        synthetic = SalesRecord.objects.filter(dataset=SalesRecord.Dataset.TRAIN)
        synthetic_rows = list(
            synthetic.values("date").annotate(quantity=Sum("quantity")).order_by("date")
        )
        real_rows = list(RealMarketRecord.objects.values("date", "cut_flowers"))
        if synthetic_rows and real_rows:
            synthetic_frame = pd.DataFrame(synthetic_rows)
            real_frame = pd.DataFrame(real_rows).rename(columns={"cut_flowers": "quantity"})
            stats = comparison_stats(synthetic_frame, real_frame)

    context = {
        "run": run,
        "stats": stats,
        "weekly_chart": weekly_comparison_chart(stats),
        "monthly_chart": monthly_comparison_chart(stats),
    }
    return render(request, "shop/comparison.html", context)
