from datetime import timedelta

import pandas as pd
from django.contrib import messages
from django.db.models import Max, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from shop.forecasting.charts import forecast_chart
from shop.forecasting.service import latest_run, run_operational_forecast
from shop.models import ModelRun, Product, Recommendation, SalesRecord
from shop.permissions import role_required


@require_GET
@role_required("manager", "admin")
def forecast_view(request):
    run = latest_run(ModelRun.Kind.OPERATIONAL)
    products = Product.objects.filter(is_active=True).order_by("name")

    if not run:
        return render(
            request,
            "shop/forecast.html",
            {"run": None, "products": products, "no_run": True},
        )

    selected = request.GET.get("product", "all")
    product = None
    if selected not in {"", "all", None}:
        product = get_object_or_404(Product, pk=selected)
        forecast_qs = run.forecasts.filter(product=product).order_by("date")
    else:
        forecast_qs = run.forecasts.order_by("date")

    if product:
        forecast_rows = list(
            forecast_qs.values(
                "date", "predicted_quantity", "lower_bound", "upper_bound", "is_peak", "holiday_name"
            )
        )
        history_rows = list(
            SalesRecord.objects.filter(
                product=product,
                date__gte=timezone.localdate() - timedelta(days=60),
                date__lte=timezone.localdate(),
            )
            .values("date")
            .annotate(quantity=Sum("quantity"))
            .order_by("date")
        )
        label = product.name
    else:
        forecast_rows = list(
            forecast_qs.values("date")
            .annotate(
                predicted_quantity=Sum("predicted_quantity"),
                lower_bound=Sum("lower_bound"),
                upper_bound=Sum("upper_bound"),
                is_peak=Max("is_peak"),
                holiday_name=Max("holiday_name"),
            )
            .order_by("date")
        )
        history_rows = list(
            SalesRecord.objects.filter(
                date__gte=timezone.localdate() - timedelta(days=60),
                date__lte=timezone.localdate(),
            )
            .values("date")
            .annotate(quantity=Sum("quantity"))
            .order_by("date")
        )
        label = "Все товары"

    forecast_frame = pd.DataFrame(forecast_rows)
    history_frame = pd.DataFrame(history_rows)
    if not forecast_frame.empty:
        # Псевдонимы для графика; исходные имена остаются для таблицы.
        forecast_frame["predicted"] = forecast_frame["predicted_quantity"]
        forecast_frame["lower"] = forecast_frame["lower_bound"]
        forecast_frame["upper"] = forecast_frame["upper_bound"]
        forecast_frame["date"] = pd.to_datetime(forecast_frame["date"])
    if not history_frame.empty:
        history_frame["date"] = pd.to_datetime(history_frame["date"])

    recommendations = run.recommendations.select_related("product")
    if product:
        recommendations = recommendations.filter(product=product)
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations = sorted(
        recommendations, key=lambda item: (priority_order.get(item.priority, 9), -item.purchase_quantity)
    )

    total_forecast = (
        float(forecast_frame["predicted_quantity"].sum()) if not forecast_frame.empty else 0
    )
    peak_count = (
        int(forecast_frame["is_peak"].astype(bool).sum()) if not forecast_frame.empty else 0
    )
    context = {
        "run": run,
        "products": products,
        "selected_product": product,
        "label": label,
        "forecast_rows": forecast_frame.to_dict("records") if not forecast_frame.empty else [],
        "recommendations": recommendations,
        "summary": run.summary,
        "total_forecast": total_forecast,
        "peak_count": peak_count,
        "total_purchase": sum(item.purchase_quantity for item in recommendations),
        "chart": forecast_chart(history_frame, forecast_frame, product_label=label),
        "no_run": False,
    }
    return render(request, "shop/forecast.html", context)


@require_POST
@role_required("manager", "admin")
def forecast_run(request):
    try:
        run = run_operational_forecast()
        messages.success(
            request,
            f"Прогноз на {run.horizon_days} дней построен. "
            f"Рекомендаций по закупке: {len(run.recommendations.all())}.",
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Не удалось построить прогноз: {exc}")
    return redirect("forecast")
