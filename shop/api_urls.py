from django.urls import include, path
from rest_framework.routers import DefaultRouter

from shop.views.api import (
    CategoryViewSet,
    ComparisonAPIView,
    DashboardSummaryAPIView,
    ForecastNowAPIView,
    ForecastViewSet,
    MetricsAPIView,
    ModelRunViewSet,
    OrderViewSet,
    PeakDateViewSet,
    ProductViewSet,
    RealMarketRecordViewSet,
    RecommendationViewSet,
    SalesRecordViewSet,
    SupplierViewSet,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="api-categories")
router.register("products", ProductViewSet, basename="api-products")
router.register("suppliers", SupplierViewSet, basename="api-suppliers")
router.register("orders", OrderViewSet, basename="api-orders")
router.register("sales", SalesRecordViewSet, basename="api-sales")
router.register("peaks", PeakDateViewSet, basename="api-peaks")
router.register("runs", ModelRunViewSet, basename="api-runs")
router.register("forecasts", ForecastViewSet, basename="api-forecasts")
router.register("recommendations", RecommendationViewSet, basename="api-recommendations")
router.register("real-market", RealMarketRecordViewSet, basename="api-real-market")

urlpatterns = [
    path("dashboard/summary/", DashboardSummaryAPIView.as_view(), name="api-dashboard-summary"),
    path("forecast/now/", ForecastNowAPIView.as_view(), name="api-forecast-now"),
    path("analytics/metrics/", MetricsAPIView.as_view(), name="api-metrics"),
    path("analytics/comparison/", ComparisonAPIView.as_view(), name="api-comparison"),
    path("", include(router.urls)),
]
