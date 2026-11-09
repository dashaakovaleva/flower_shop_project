"""Создаёт демонстрационные заказы для дашборда и проверки бизнес-логики."""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from shop.models import Customer, Order, Product, User
from shop.services import StockError, change_order_status, create_order


class Command(BaseCommand):
    help = "Создаёт демонстрационные заказы с разными статусами"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=28)

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(17)
        products = list(Product.objects.filter(is_active=True, stock_quantity__gt=0))
        customers = list(Customer.objects.all())
        manager = User.objects.filter(role=User.Role.MANAGER).first()
        if not products or not customers:
            self.stderr.write(self.style.ERROR("Сначала выполните seed_reference."))
            return

        existing = Order.objects.filter(comment="Демонстрационный заказ").count()
        if existing >= options["count"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Демонстрационные заказы уже созданы ({existing}), пропуск."
                )
            )
            return

        created = 0
        statuses = [
            Order.Status.NEW,
            Order.Status.PROCESSING,
            Order.Status.READY,
            Order.Status.COMPLETED,
            Order.Status.CANCELLED,
        ]
        for _ in range(options["count"]):
            chosen = rng.sample(products, k=rng.randint(1, 3))
            items = []
            for product in chosen:
                max_qty = min(3, product.stock_quantity)
                if max_qty <= 0:
                    continue
                items.append((product.id, rng.randint(1, max_qty)))
            if not items:
                continue
            try:
                order = create_order(
                    customer=rng.choice(customers),
                    items=items,
                    manager=manager,
                    delivery_date=timezone.localdate() + timedelta(days=rng.randint(0, 5)),
                    delivery_address="Москва, демонстрационный адрес",
                    comment="Демонстрационный заказ",
                    source=rng.choice([Order.Source.ONLINE, Order.Source.OFFLINE]),
                )
            except StockError:
                continue

            target_status = rng.choice(statuses)
            if target_status != Order.Status.NEW:
                try:
                    change_order_status(order, target_status)
                except StockError:
                    pass
            Order.objects.filter(pk=order.pk).update(
                created_at=timezone.now() - timedelta(days=rng.randint(0, 45))
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Создано демонстрационных заказов: {created}. "
                f"Всего заказов: {Order.objects.count()}."
            )
        )
