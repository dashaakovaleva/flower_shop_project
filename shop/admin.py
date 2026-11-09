from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

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
    Supply,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Роль и контакты", {"fields": ("role", "phone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Роль и контакты", {"fields": ("role", "phone")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_superuser")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "accent")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "category",
        "price",
        "stock_quantity",
        "min_stock",
        "is_active",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name", "sku")
    list_editable = ("price", "stock_quantity", "min_stock", "is_active")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "email", "is_active")
    search_fields = ("name", "contact_person", "email")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "customer_type", "phone", "email", "user")
    list_filter = ("customer_type",)
    search_fields = ("full_name", "company_name", "phone", "email", "inn")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("line_total",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "status", "source", "created_at", "total_amount")
    list_filter = ("status", "source", "created_at")
    search_fields = ("id", "customer__full_name", "customer__company_name")
    inlines = [OrderItemInline]
    readonly_fields = ("created_at", "updated_at", "stock_deducted")


@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    list_display = ("product", "supplier", "quantity", "purchase_price", "supply_date")
    list_filter = ("supplier", "supply_date")
    search_fields = ("product__name", "supplier__name")


@admin.register(PeakDate)
class PeakDateAdmin(admin.ModelAdmin):
    list_display = ("name", "month", "day", "demand_coefficient", "window_days")
    ordering = ("month", "day")


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = ("date", "product", "quantity", "revenue", "dataset", "is_peak", "holiday_name")
    list_filter = ("dataset", "is_peak", "holiday_name")
    search_fields = ("product__name",)
    date_hierarchy = "date"


@admin.register(RealMarketRecord)
class RealMarketRecordAdmin(admin.ModelAdmin):
    list_display = ("date", "cut_flowers", "pot_own", "pot_purchased", "commodity")
    date_hierarchy = "date"


class ModelMetricInline(admin.TabularInline):
    model = ModelMetric
    extra = 0
    readonly_fields = ("segment", "n_obs", "mae", "rmse", "mape", "wape", "bias_pct")


@admin.register(ModelRun)
class ModelRunAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "model_name", "status", "created_at", "train_start", "test_end")
    list_filter = ("kind", "status", "model_name")
    inlines = [ModelMetricInline]
    readonly_fields = ("created_at", "summary", "params", "error_message")


@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = ("date", "product", "predicted_quantity", "actual_quantity", "is_peak", "run")
    list_filter = ("run", "is_peak")
    search_fields = ("product__name",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "priority",
        "forecast_demand",
        "current_stock",
        "purchase_quantity",
        "run",
    )
    list_filter = ("priority", "run")


admin.site.site_header = "FloraIS — административная панель"
admin.site.site_title = "FloraIS"
admin.site.index_title = "Управление системой"
