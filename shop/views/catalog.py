from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from shop.forms import CheckoutForm
from shop.models import Category, Order, Product
from shop.services import Cart, StockError, change_order_status, create_order, get_or_create_customer_for_user


@require_GET
def catalog(request):
    products = Product.objects.filter(is_active=True).select_related("category")
    categories = Category.objects.all()
    category_slug = request.GET.get("category", "").strip()
    search = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "name")

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if search:
        products = products.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(sku__icontains=search)
        )

    sort_map = {
        "name": "name",
        "price_asc": "price",
        "price_desc": "-price",
        "new": "-created_at",
    }
    products = products.order_by(sort_map.get(sort, "name"))

    context = {
        "products": products,
        "categories": categories,
        "active_category": category_slug,
        "search": search,
        "sort": sort,
        "cart": Cart(request),
    }
    return render(request, "shop/catalog.html", context)


@require_GET
def product_detail(request, pk: int):
    product = get_object_or_404(Product.objects.select_related("category"), pk=pk)
    related = (
        Product.objects.filter(category=product.category, is_active=True)
        .exclude(pk=product.pk)[:4]
    )
    return render(
        request,
        "shop/product_detail.html",
        {"product": product, "related": related},
    )


@require_POST
@login_required
def cart_add(request, pk: int):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    quantity = max(1, int(request.POST.get("quantity", 1) or 1))
    cart = Cart(request)
    try:
        cart.add(product, quantity)
        messages.success(request, f"«{product.name}» добавлен в корзину.")
    except StockError as exc:
        messages.error(request, str(exc))
    next_url = request.POST.get("next") or reverse("catalog")
    return redirect(next_url)


@require_POST
@login_required
def cart_update(request, pk: int):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    quantity = int(request.POST.get("quantity", 1) or 0)
    cart = Cart(request)
    try:
        cart.set_quantity(product, quantity)
    except (StockError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("cart")


@require_POST
@login_required
def cart_remove(request, pk: int):
    product = get_object_or_404(Product, pk=pk)
    Cart(request).remove(product)
    messages.info(request, f"«{product.name}» удалён из корзины.")
    return redirect("cart")


@require_GET
@login_required
def cart_view(request):
    cart = Cart(request)
    return render(request, "shop/cart.html", {"cart": cart, "items": cart.items()})


@require_http_methods(["GET", "POST"])
@login_required
def checkout(request):
    cart = Cart(request)
    items = cart.items()
    if not items:
        messages.info(request, "Корзина пуста — добавьте товары из каталога.")
        return redirect("catalog")

    customer = get_or_create_customer_for_user(request.user)
    form = CheckoutForm(
        request.POST or None,
        initial={
            "delivery_address": customer.address,
            "customer_type": customer.customer_type,
            "company_name": customer.company_name,
            "inn": customer.inn,
        },
    )

    if request.method == "POST" and form.is_valid():
        customer.customer_type = form.cleaned_data["customer_type"]
        customer.company_name = form.cleaned_data.get("company_name", "")
        customer.inn = form.cleaned_data.get("inn", "")
        customer.address = form.cleaned_data["delivery_address"]
        customer.phone = customer.phone or request.user.phone
        customer.email = customer.email or request.user.email
        customer.save()

        try:
            order = create_order(
                customer=customer,
                items=cart.as_items(),
                manager=None,
                delivery_date=form.cleaned_data.get("delivery_date"),
                delivery_address=form.cleaned_data["delivery_address"],
                comment=form.cleaned_data.get("comment", ""),
                source=Order.Source.ONLINE,
            )
        except StockError as exc:
            messages.error(request, f"Не удалось оформить заказ: {exc}")
        else:
            cart.clear()
            messages.success(
                request,
                f"Заказ {order.number} оформлен. Мы свяжемся с вами для подтверждения.",
            )
            return redirect("order_detail", pk=order.pk)

    return render(
        request,
        "shop/checkout.html",
        {"form": form, "items": items, "cart": cart},
    )


@require_GET
@login_required
def my_orders(request):
    if getattr(request.user, "is_manager", False):
        return redirect("manager_orders")
    customer = get_or_create_customer_for_user(request.user)
    orders = customer.orders.prefetch_related("items__product").all()
    return render(request, "shop/my_orders.html", {"orders": orders, "customer": customer})


@require_GET
@login_required
def order_detail(request, pk: int):
    order = get_object_or_404(
        Order.objects.select_related("customer", "manager").prefetch_related(
            "items__product"
        ),
        pk=pk,
    )
    customer = getattr(request.user, "customer_profile", None)
    if not getattr(request.user, "is_manager", False) and (
        not customer or order.customer_id != customer.id
    ):
        messages.error(request, "У вас нет доступа к этому заказу.")
        return redirect("home")
    return render(request, "shop/order_detail.html", {"order": order})


@require_POST
@login_required
def order_cancel(request, pk: int):
    order = get_object_or_404(Order, pk=pk)
    customer = getattr(request.user, "customer_profile", None)
    if not getattr(request.user, "is_manager", False) and (
        not customer or order.customer_id != customer.id
    ):
        messages.error(request, "У вас нет доступа к этому заказу.")
        return redirect("home")
    try:
        change_order_status(order, Order.Status.CANCELLED)
        messages.success(request, f"Заказ {order.number} отменён, остатки возвращены.")
    except StockError as exc:
        messages.error(request, str(exc))
    return redirect("order_detail", pk=order.pk)
