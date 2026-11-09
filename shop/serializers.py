"""DRF-сериализаторы для REST API информационной системы."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Category,
    Customer,
    Forecast,
    ModelMetric,
    ModelRun,
    Order,
    OrderItem,
    PeakDate,
    Product,
    RealMarketRecord,
    Recommendation,
    SalesRecord,
    Supplier,
)
from .services import create_order


class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "icon", "accent", "products_count")


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    stock_status = serializers.CharField(read_only=True)
    margin_percent = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "category",
            "category_name",
            "name",
            "sku",
            "description",
            "price",
            "cost_price",
            "stock_quantity",
            "min_stock",
            "unit",
            "image_emoji",
            "is_active",
            "stock_status",
            "margin_percent",
        )


class CustomerSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Customer
        fields = (
            "id",
            "user",
            "customer_type",
            "full_name",
            "company_name",
            "inn",
            "phone",
            "email",
            "address",
            "display_name",
        )


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "quantity", "price_at_moment", "line_total")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    manager_name = serializers.CharField(source="manager.username", read_only=True)
    number = serializers.CharField(read_only=True)
    status_label = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "number",
            "customer",
            "customer_name",
            "manager",
            "manager_name",
            "status",
            "status_label",
            "source",
            "created_at",
            "delivery_date",
            "delivery_address",
            "comment",
            "total_amount",
            "items",
        )


class OrderItemInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    quantity = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True
    )
    manager = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(role__in=["manager", "admin"]),
        required=False,
        allow_null=True,
    )
    delivery_date = serializers.DateField(required=False, allow_null=True)
    delivery_address = serializers.CharField(required=False, allow_blank=True, default="")
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    source = serializers.ChoiceField(choices=Order.Source.choices, default=Order.Source.OFFLINE)
    items = OrderItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Нужна хотя бы одна позиция заказа.")
        return value

    def create(self, validated_data):
        items = [(item["product"].id, item["quantity"]) for item in validated_data.pop("items")]
        return create_order(items=items, **validated_data)


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ("id", "name", "contact_person", "phone", "email", "address", "is_active")


class PeakDateSerializer(serializers.ModelSerializer):
    days_until = serializers.SerializerMethodField()
    next_occurrence = serializers.SerializerMethodField()

    def get_days_until(self, obj):
        return obj.days_until()

    def get_next_occurrence(self, obj):
        return obj.next_occurrence()

    class Meta:
        model = PeakDate
        fields = (
            "id",
            "name",
            "month",
            "day",
            "demand_coefficient",
            "window_days",
            "color",
            "description",
            "days_until",
            "next_occurrence",
        )


class SalesRecordSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    dataset_label = serializers.CharField(source="get_dataset_display", read_only=True)

    class Meta:
        model = SalesRecord
        fields = (
            "id",
            "product",
            "product_name",
            "date",
            "quantity",
            "revenue",
            "dataset",
            "dataset_label",
            "is_peak",
            "holiday_name",
            "promo",
        )


class RealMarketRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealMarketRecord
        fields = (
            "id",
            "date",
            "cut_flowers",
            "pot_own",
            "pot_purchased",
            "wholesale",
            "fruits_vegs",
            "commodity",
            "mean_temp",
            "mean_humidity",
            "public_holiday",
            "school_holiday",
            "source",
        )


class ModelMetricSerializer(serializers.ModelSerializer):
    segment_label = serializers.CharField(source="get_segment_display", read_only=True)

    class Meta:
        model = ModelMetric
        fields = (
            "id",
            "segment",
            "segment_label",
            "n_obs",
            "mae",
            "rmse",
            "mape",
            "wape",
            "bias_pct",
            "coverage_pct",
            "actual_mean",
            "predicted_mean",
        )


class ModelRunSerializer(serializers.ModelSerializer):
    metrics = ModelMetricSerializer(many=True, read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ModelRun
        fields = (
            "id",
            "kind",
            "kind_label",
            "model_name",
            "status",
            "status_label",
            "train_start",
            "train_end",
            "test_start",
            "test_end",
            "horizon_days",
            "created_at",
            "params",
            "summary",
            "metrics",
        )


class ForecastSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    error = serializers.FloatField(read_only=True)

    class Meta:
        model = Forecast
        fields = (
            "id",
            "run",
            "product",
            "product_name",
            "date",
            "predicted_quantity",
            "lower_bound",
            "upper_bound",
            "actual_quantity",
            "error",
            "is_peak",
            "holiday_name",
        )


class RecommendationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    priority_label = serializers.CharField(read_only=True)
    coverage_percent = serializers.FloatField(read_only=True)

    class Meta:
        model = Recommendation
        fields = (
            "id",
            "run",
            "product",
            "product_name",
            "horizon_days",
            "forecast_demand",
            "current_stock",
            "safety_stock",
            "required_stock",
            "purchase_quantity",
            "priority",
            "priority_label",
            "coverage_percent",
            "reason",
            "created_at",
        )
