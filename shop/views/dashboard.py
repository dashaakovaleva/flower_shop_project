from datetime import timedelta

import pandas as pd
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from shop.forecasting.charts import revenue_chart, top_products_chart
from shop.forecasting.service import latest_run
from shop.models import ModelRun, Order, PeakDate, Product, Recommendation, SalesRecord
from shop.permissions import role_required


@require_GET
@role_required("manager", "admin")
def dashboard(request):
    today = timezone.localdate()
    last_30_start = today - timedelta(days=29)
    previous_30_start = today - timedelta(days=59)
    previous_30_end = today - timedelta(days=30)

    sales = SalesRecord.objects.all()
    current_sales = sales.filter(date__gte=last_30_start, date__lte=today)
    previous_sales = sales.filter(date__gte=previous_30_start, date__lte=previous_30_end)

    current_revenue = current_sales.aggregate(total=Sum("revenue"))["total"] or 0
    previous_revenue = previous_sales.aggregate(total=Sum("revenue"))["total"] or 0
    current_quantity = current_sales.aggregate(total=Sum("quantity"))["total"] or 0
    previous_quantity = previous_sales.aggregate(total=Sum("quantity"))["total"] or 0

    def growth(current, previous):
        if not previous:
            return None
        return round((float(current) - float(previous)) / float(previous) * 100, 1)

    orders_30 = Order.objects.filter(created_at__date__gte=last_30_start)
    avg_check = (
        orders_30.aggregate(total=Sum("total_amount"))["total"] or 0
    ) / max(orders_30.count(), 1)

    daily_rows = (
        current_sales.values("date")
        .annotate(revenue=Sum("revenue"), quantity=Sum("quantity"))
        .order_by("date")
    )
    daily_frame = pd.DataFrame(list(daily_rows))
    if not daily_frame.empty:
        daily_frame["date"] = pd.to_datetime(daily_frame["date"])

    top_rows = (
        current_sales.values("product__name")
        .annotate(revenue=Sum("revenue"), quantity=Sum("quantity"))
        .order_by("-revenue")[:10]
    )
    top_frame = pd.DataFrame(list(top_rows))
    if not top_frame.empty:
        top_frame = top_frame.rename(columns={"product__name": "product__name"})

    operational = latest_run(ModelRun.Kind.OPERATIONAL)
    backtest = latest_run(ModelRun.Kind.BACKTEST)
    recommendations = []
    if operational:
        recommendations = list(
            operational.recommendations.select_related("product").order_by(
                "priority", "-purchase_quantity"
            )[:8]
        )

    # Выбираем товары, где остаток ниже минимального.
    low_stock = [
        product
        for product in Product.objects.filter(is_active=True)
        if product.stock_quantity <= product.min_stock
    ]

    upcoming_peaks = []
    for peak in PeakDate.objects.all():
        days = peak.days_until(today)
        if days <= 120:
            upcoming_peaks.append(
                {
                    "name": peak.name,
                    "date": peak.next_occurrence(today),
                    "days": days,
                    "color": peak.color,
                }
            )
    upcoming_peaks.sort(key=lambda item: item["days"])

    context = {
        "revenue_30": current_revenue,
        "revenue_growth": growth(current_revenue, previous_revenue),
        "quantity_30": current_quantity,
        "quantity_growth": growth(current_quantity, previous_quantity),
        "orders_30": orders_30.count(),
        "avg_check": avg_check,
        "products_count": Product.objects.filter(is_active=True).count(),
        "low_stock_count": len(low_stock),
        "low_stock": low_stock[:6],
        "recommendations": recommendations,
        "operational": operational,
        "backtest": backtest,
        "mape": backtest.metric("all").mape if backtest else None,
        "peak_mape": backtest.metric("peak").mape if backtest else None,
        "upcoming_peaks": upcoming_peaks[:5],
        "recent_orders": Order.objects.select_related("customer", "manager")[:8],
        "revenue_chart": revenue_chart(daily_frame, "Выручка за последние 30 дней"),
        "top_chart": top_products_chart(top_frame, "Топ товаров за 30 дней"),
        "recommendation_count": len(recommendations),
    }
    return render(request, "shop/dashboard.html", context)
