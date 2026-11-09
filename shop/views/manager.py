from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from shop.forms import ProductEditForm, SupplyForm
from shop.models import Category, Order, Product, Supply
from shop.permissions import role_required
from shop.services import StockError, change_order_status, receive_supply


@require_GET
@role_required("manager", "admin")
def manager_orders(request):
    orders = Order.objects.select_related("customer", "manager").prefetch_related("items")
    status = request.GET.get("status", "").strip()
    search = request.GET.get("q", "").strip()
    if status:
        orders = orders.filter(status=status)
    if search:
        orders = orders.filter(
            Q(customer__full_name__icontains=search)
            | Q(customer__company_name__icontains=search)
            | Q(id__icontains=search)
        )
    context = {
        "orders": orders,
        "status_filter": status,
        "search": search,
        "status_options": Order.Status.choices,
        "status_counts": {
            value: Order.objects.filter(status=value).count()
            for value, _ in Order.Status.choices
        },
    }
    return render(request, "shop/manager/orders.html", context)


@require_POST
@role_required("manager", "admin")
def order_status_update(request, pk: int):
    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get("status", "")
    try:
        change_order_status(order, new_status)
        messages.success(
            request,
            f"Статус заказа {order.number} изменён на «{order.get_status_display()}».",
        )
    except (StockError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect(request.POST.get("next") or "manager_orders")


@require_GET
@role_required("manager", "admin")
def manager_products(request):
    products = Product.objects.select_related("category").all()
    search = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    low_only = request.GET.get("low", "") == "1"
    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    if category:
        products = products.filter(category__slug=category)
    if low_only:
        products = [product for product in products if product.stock_quantity <= product.min_stock]
    context = {
        "products": products,
        "categories": Category.objects.all(),
        "search": search,
        "active_category": category,
        "low_only": low_only,
    }
    return render(request, "shop/manager/products.html", context)


@require_http_methods(["GET", "POST"])
@role_required("manager", "admin")
def product_edit(request, pk: int):
    product = get_object_or_404(Product, pk=pk)
    form = ProductEditForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Товар «{product.name}» обновлён.")
        return redirect("manager_products")
    return render(
        request,
        "shop/manager/product_edit.html",
        {"product": product, "form": form},
    )


@require_http_methods(["GET", "POST"])
@role_required("manager", "admin")
def manager_supplies(request):
    form = SupplyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            receive_supply(
                supplier=data["supplier"],
                product=data["product"],
                quantity=data["quantity"],
                purchase_price=data["purchase_price"],
                supply_date=data["supply_date"],
                comment=data.get("comment", ""),
            )
            messages.success(
                request,
                f"Поставка {data['product'].name} на {data['quantity']} шт. принята на склад.",
            )
            return redirect("manager_supplies")
        except StockError as exc:
            messages.error(request, str(exc))

    context = {
        "form": form,
        "supplies": Supply.objects.select_related("product", "supplier")[:40],
    }
    return render(request, "shop/manager/supplies.html", context)
