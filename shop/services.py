"""Бизнес-логика заказов и поставок: списание и восстановление остатков."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from .models import Customer, Order, OrderItem, Product, Supply, User


class StockError(ValueError):
    """Недостаточно товара на складе или некорректное количество."""


@transaction.atomic
def create_order(
    *,
    customer: Customer,
    items: list[tuple[int, int]],
    manager: User | None = None,
    delivery_date=None,
    delivery_address: str = "",
    comment: str = "",
    source: str = Order.Source.ONLINE,
    status: str = Order.Status.NEW,
) -> Order:
    """Создаёт заказ, проверяет остатки и атомарно списывает товар.

    items: список пар (product_id, quantity).
    """

    if not items:
        raise StockError("Заказ не может быть пустым.")

    product_ids = [product_id for product_id, _ in items]
    products = {
        product.id: product
        for product in Product.objects.select_for_update().filter(id__in=product_ids)
    }

    order = Order.objects.create(
        customer=customer,
        manager=manager,
        delivery_date=delivery_date,
        delivery_address=delivery_address,
        comment=comment,
        source=source,
        status=status,
        stock_deducted=True,
    )

    total = Decimal("0")
    for product_id, quantity in items:
        if quantity <= 0:
            raise StockError("Количество товара должно быть больше нуля.")
        product = products.get(product_id)
        if product is None:
            raise StockError("Товар не найден.")
        if product.stock_quantity < quantity:
            raise StockError(
                f"«{product.name}»: на складе {product.stock_quantity} шт., "
                f"запрошено {quantity} шт."
            )

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price_at_moment=product.price,
        )
        product.stock_quantity -= quantity
        product.save(update_fields=["stock_quantity"])
        total += product.price * quantity

    order.total_amount = total
    order.save(update_fields=["total_amount"])
    return order


@transaction.atomic
def change_order_status(order: Order, new_status: str) -> Order:
    """Меняет статус заказа, корректно возвращая остатки при отмене."""

    if new_status not in Order.Status.values:
        raise StockError("Неизвестный статус заказа.")
    if new_status == order.status:
        return order

    if new_status == Order.Status.CANCELLED and order.stock_deducted:
        for item in order.items.select_related("product"):
            product = Product.objects.select_for_update().get(id=item.product_id)
            product.stock_quantity += item.quantity
            product.save(update_fields=["stock_quantity"])
        order.stock_deducted = False
    elif order.status == Order.Status.CANCELLED and new_status != Order.Status.CANCELLED:
        # Повторное открытие отменённого заказа: проверяем и снова списываем остатки.
        for item in order.items.select_related("product"):
            product = Product.objects.select_for_update().get(id=item.product_id)
            if product.stock_quantity < item.quantity:
                raise StockError(
                    f"Нельзя восстановить заказ: «{product.name}» осталось "
                    f"{product.stock_quantity} шт., нужно {item.quantity} шт."
                )
            product.stock_quantity -= item.quantity
            product.save(update_fields=["stock_quantity"])
        order.stock_deducted = True

    order.status = new_status
    order.save(update_fields=["status", "stock_deducted", "updated_at"])
    return order


@transaction.atomic
def receive_supply(
    *,
    supplier,
    product: Product,
    quantity: int,
    purchase_price,
    supply_date,
    comment: str = "",
) -> Supply:
    """Регистрирует поставку и увеличивает остаток товара."""

    if quantity <= 0:
        raise StockError("Количество поставки должно быть больше нуля.")

    product = Product.objects.select_for_update().get(id=product.id)
    supply = Supply.objects.create(
        supplier=supplier,
        product=product,
        quantity=quantity,
        purchase_price=purchase_price,
        supply_date=supply_date,
        comment=comment,
    )
    product.stock_quantity += quantity
    product.save(update_fields=["stock_quantity"])
    return supply


def get_or_create_customer_for_user(user: User) -> Customer:
    """Возвращает профиль клиента, создавая его при необходимости."""

    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "full_name": user.get_full_name() or user.username,
            "phone": user.phone,
            "email": user.email,
            "customer_type": Customer.CustomerType.PHYSICAL,
        },
    )
    return customer


class Cart:
    """Корзина в сессии: {product_id: quantity}."""

    SESSION_KEY = "cart"

    def __init__(self, request):
        self.request = request
        self.session = request.session
        self.data = self.session.get(self.SESSION_KEY, {})

    def add(self, product: Product, quantity: int = 1) -> None:
        if quantity <= 0:
            raise StockError("Количество должно быть больше нуля.")
        current = int(self.data.get(str(product.id), 0))
        new_quantity = current + quantity
        if new_quantity > product.stock_quantity:
            raise StockError(
                f"«{product.name}»: доступно только {product.stock_quantity} шт."
            )
        self.data[str(product.id)] = new_quantity
        self.save()

    def set_quantity(self, product: Product, quantity: int) -> None:
        if quantity <= 0:
            self.remove(product)
            return
        if quantity > product.stock_quantity:
            raise StockError(
                f"«{product.name}»: доступно только {product.stock_quantity} шт."
            )
        self.data[str(product.id)] = quantity
        self.save()

    def remove(self, product: Product) -> None:
        self.data.pop(str(product.id), None)
        self.save()

    def clear(self) -> None:
        self.session[self.SESSION_KEY] = {}
        self.session.modified = True
        self.data = {}

    def save(self) -> None:
        self.session[self.SESSION_KEY] = self.data
        self.session.modified = True

    def __len__(self) -> int:
        return sum(int(qty) for qty in self.data.values())

    def items(self):
        product_ids = [int(pid) for pid in self.data.keys()]
        products = Product.objects.filter(id__in=product_ids, is_active=True)
        result = []
        for product in products:
            quantity = int(self.data.get(str(product.id), 0))
            if quantity:
                result.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "line_total": product.price * quantity,
                    }
                )
        return result

    def total(self) -> Decimal:
        return sum((item["line_total"] for item in self.items()), Decimal("0"))

    def as_items(self) -> list[tuple[int, int]]:
        return [(int(pid), int(qty)) for pid, qty in self.data.items() if int(qty) > 0]
