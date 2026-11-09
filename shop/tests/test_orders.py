from decimal import Decimal

from django.test import TestCase

from shop.models import Category, Customer, Order, Product, Supplier
from shop.services import StockError, change_order_status, create_order, receive_supply


class OrderServiceTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Розы", slug="roses")
        self.product = Product.objects.create(
            category=self.category,
            name="Роза красная",
            sku="ROSE-001",
            price=Decimal("150.00"),
            cost_price=Decimal("80.00"),
            stock_quantity=20,
            min_stock=5,
        )
        self.customer = Customer.objects.create(full_name="Иванов Иван")

    def test_create_order_deducts_stock_and_sets_total(self):
        order = create_order(
            customer=self.customer,
            items=[(self.product.id, 3)],
            delivery_address="Москва",
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 17)
        self.assertEqual(order.total_amount, Decimal("450.00"))
        self.assertTrue(order.stock_deducted)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().price_at_moment, Decimal("150.00"))

    def test_create_order_rejects_insufficient_stock_atomically(self):
        with self.assertRaises(StockError):
            create_order(
                customer=self.customer,
                items=[(self.product.id, 100)],
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertEqual(Order.objects.count(), 0)

    def test_create_order_rejects_empty_items(self):
        with self.assertRaises(StockError):
            create_order(customer=self.customer, items=[])
        self.assertEqual(Order.objects.count(), 0)

    def test_cancel_returns_stock_and_reopen_deducts_again(self):
        order = create_order(
            customer=self.customer,
            items=[(self.product.id, 4)],
        )
        change_order_status(order, Order.Status.CANCELLED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertFalse(order.stock_deducted)

        change_order_status(order, Order.Status.PROCESSING)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 16)
        self.assertTrue(order.stock_deducted)

    def test_supply_increases_stock_and_creates_record(self):
        supplier = Supplier.objects.create(name="ЦветОпт")
        supply = receive_supply(
            supplier=supplier,
            product=self.product,
            quantity=12,
            purchase_price=Decimal("70.00"),
            supply_date="2026-01-10",
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 32)
        self.assertEqual(supply.quantity, 12)
