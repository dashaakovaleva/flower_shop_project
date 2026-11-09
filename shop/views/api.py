"""REST API информационной системы."""

from datetime import timedelta

from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shop.forecasting.service import latest_run, run_operational_forecast
from shop.models import (
    Category,
    Forecast,
    ModelRun,
    Order,
    PeakDate,
    Product,
    RealMarketRecord,
    Recommendation,
    SalesRecord,
    Supplier,
)
from shop.permissions import (
    IsManagerOrAdmin,
    IsManagerOrAdminOrReadOnly,
    IsOwnerOrManager,
    user_has_role,
)
from shop.serializers import (
    CategorySerializer,
    ForecastSerializer,
    ModelRunSerializer,
    OrderCreateSerializer,
    OrderSerializer,
    OrderStatusSerializer,
    PeakDateSerializer,
    ProductSerializer,
    RealMarketRecordSerializer,
    RecommendationSerializer,
    SalesRecordSerializer,
    SupplierSerializer,
)
from shop.services import StockError, change_order_status, get_or_create_customer_for_user


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]
    search_fields = ["name"]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category").all()
    serializer_class = ProductSerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]
    search_fields = ["name", "sku", "description"]
    ordering_fields = ["name", "price", "stock_quantity", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not user_has_role(self.request.user, "manager", "admin"):
            queryset = queryset.filter(is_active=True)
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)
        if self.request.query_params.get("low") == "1":
            queryset = queryset.filter(stock_quantity__lte=F("min_stock"))
        return queryset


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsManagerOrAdmin]
    search_fields = ["name", "contact_person", "email"]


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related("customer", "manager").prefetch_related("items__product")
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if user_has_role(self.request.user, "manager", "admin"):
            return queryset
        customer = getattr(self.request.user, "customer_profile", None)
        return queryset.filter(customer=customer) if customer else queryset.none()

    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        if not user_has_role(request.user, "manager", "admin"):
            validated["customer"] = get_or_create_customer_for_user(request.user)
            validated["manager"] = None
            validated["source"] = Order.Source.ONLINE
        else:
            if not validated.get("customer"):
                return Response(
                    {"customer": ["Укажите клиента для заказа, создаваемого менеджером."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not validated.get("manager"):
                validated["manager"] = request.user
        try:
            order = serializer.save()
        except StockError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def set_status(self, request, pk=None):
        if not user_has_role(request.user, "manager", "admin"):
            return Response(
                {"detail": "Недостаточно прав."}, status=status.HTTP_403_FORBIDDEN
            )
        order = self.get_object()
        serializer = OrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            change_order_status(order, serializer.validated_data["status"])
        except StockError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        self.check_object_permissions(request, order)
        try:
            change_order_status(order, Order.Status.CANCELLED)
        except StockError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data)


class SalesRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SalesRecord.objects.select_related("product").all()
    serializer_class = SalesRecordSerializer
    permission_classes = [IsManagerOrAdmin]
    search_fields = ["product__name", "holiday_name"]
    ordering = ["-date"]

    def get_queryset(self):
        queryset = super().get_queryset()
        product = self.request.query_params.get("product")
        dataset = self.request.query_params.get("dataset")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if product:
            queryset = queryset.filter(product_id=product)
        if dataset:
            queryset = queryset.filter(dataset=dataset)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        return queryset


class PeakDateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PeakDate.objects.all()
    serializer_class = PeakDateSerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]


class ModelRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ModelRun.objects.prefetch_related("metrics").all()
    serializer_class = ModelRunSerializer
    permission_classes = [IsManagerOrAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        kind = self.request.query_params.get("kind")
        return queryset.filter(kind=kind) if kind else queryset


class ForecastViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Forecast.objects.select_related("product").all()
    serializer_class = ForecastSerializer
    permission_classes = [IsManagerOrAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        run = self.request.query_params.get("run")
        product = self.request.query_params.get("product")
        if run:
            queryset = queryset.filter(run_id=run)
        if product:
            queryset = queryset.filter(product_id=product)
        return queryset.order_by("date", "product")


class RecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Recommendation.objects.select_related("product").all()
    serializer_class = RecommendationSerializer
    permission_classes = [IsManagerOrAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        run = self.request.query_params.get("run")
        priority = self.request.query_params.get("priority")
        if run:
            queryset = queryset.filter(run_id=run)
        if priority:
            queryset = queryset.filter(priority=priority)
        return queryset


class RealMarketRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RealMarketRecord.objects.all()
    serializer_class = RealMarketRecordSerializer
    permission_classes = [IsManagerOrAdmin]
    ordering = ["date"]


class DashboardSummaryAPIView(APIView):
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        today = timezone.localdate()
        start = today - timedelta(days=29)
        sales = SalesRecord.objects.filter(date__gte=start, date__lte=today)
        operational = latest_run(ModelRun.Kind.OPERATIONAL)
        backtest = latest_run(ModelRun.Kind.BACKTEST)
        low_stock = [
            {
                "id": product.id,
                "name": product.name,
                "stock": product.stock_quantity,
                "min_stock": product.min_stock,
            }
            for product in Product.objects.filter(is_active=True)
            if product.stock_quantity <= product.min_stock
        ]
        return Response(
            {
                "period_days": 30,
                "revenue": float(sales.aggregate(total=Sum("revenue"))["total"] or 0),
                "quantity": int(sales.aggregate(total=Sum("quantity"))["total"] or 0),
                "orders": Order.objects.filter(created_at__date__gte=start).count(),
                "low_stock": low_stock,
                "latest_operational_run": ModelRunSerializer(operational).data if operational else None,
                "latest_backtest_run": ModelRunSerializer(backtest).data if backtest else None,
            }
        )


class ForecastNowAPIView(APIView):
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        run = latest_run(ModelRun.Kind.OPERATIONAL)
        if not run:
            return Response(
                {"detail": "Рабочий прогноз ещё не построен."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "run": ModelRunSerializer(run).data,
                "recommendations": RecommendationSerializer(
                    run.recommendations.select_related("product"), many=True
                ).data,
            }
        )

    def post(self, request):
        try:
            run = run_operational_forecast()
        except Exception as exc:  # noqa: BLE001
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "run": ModelRunSerializer(run).data,
                "recommendations": RecommendationSerializer(
                    run.recommendations.select_related("product"), many=True
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class MetricsAPIView(APIView):
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        run = latest_run(ModelRun.Kind.BACKTEST)
        if not run:
            return Response(
                {"detail": "Бэктест ещё не выполнялся."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ModelRunSerializer(run).data)


class ComparisonAPIView(APIView):
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        run = latest_run(ModelRun.Kind.BACKTEST)
        if not run:
            return Response(
                {"detail": "Бэктест ещё не выполнялся."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "run_id": run.id,
                "comparison": (run.summary or {}).get("comparison", {}),
            }
        )
