from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from shop.models import Category, ModelRun, PeakDate, Product


@require_GET
def home(request):
    """Лендинг для гостя и маршрутизация авторизованных пользователей."""

    if request.user.is_authenticated:
        if getattr(request.user, "is_manager", False):
            return redirect("dashboard")
        return redirect("catalog")

    latest_backtest = (
        ModelRun.objects.filter(
            kind=ModelRun.Kind.BACKTEST, status=ModelRun.Status.COMPLETED
        )
        .order_by("-created_at")
        .first()
    )
    context = {
        "products_count": Product.objects.filter(is_active=True).count(),
        "categories": Category.objects.all(),
        "peaks": PeakDate.objects.all(),
        "latest_backtest": latest_backtest,
        "mape": latest_backtest.metric("all").mape if latest_backtest else None,
    }
    return render(request, "shop/landing.html", context)


@require_GET
def docs_view(request):
    return render(request, "shop/docs.html")
