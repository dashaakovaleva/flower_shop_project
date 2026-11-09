from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from shop.models import Category, Customer, Order, Product, User
from shop.services import create_order


class RoleAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Букеты", slug="bouquets")
        cls.product = Product.objects.create(
            category=cls.category,
            name="Букет весенний",
            sku="BQ-001",
            price=Decimal("2500.00"),
            cost_price=Decimal("1500.00"),
            stock_quantity=10,
        )
        cls.client_user = User.objects.create_user(
            username="client1", password="pass12345", role=User.Role.CLIENT
        )
        cls.other_user = User.objects.create_user(
            username="client2", password="pass12345", role=User.Role.CLIENT
        )
        cls.manager = User.objects.create_user(
            username="manager1", password="pass12345", role=User.Role.MANAGER
        )
        cls.customer = Customer.objects.create(
            user=cls.client_user, full_name="Клиент Один"
        )
        cls.other_customer = Customer.objects.create(
            user=cls.other_user, full_name="Клиент Два"
        )
        cls.order = create_order(
            customer=cls.customer,
            items=[(cls.product.id, 1)],
        )
        cls.other_order = create_order(
            customer=cls.other_customer,
            items=[(cls.product.id, 1)],
        )

    def test_anonymous_is_redirected_from_private_pages(self):
        for url in ("/dashboard/", "/forecast/", "/analytics/", "/my-orders/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn("/login/", response["Location"])

    def test_client_cannot_open_manager_pages(self):
        self.client.login(username="client1", password="pass12345")
        for url in ("/dashboard/", "/forecast/", "/analytics/", "/manager/orders/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_manager_can_open_manager_pages(self):
        self.client.login(username="manager1", password="pass12345")
        for url in (
            "/dashboard/",
            "/forecast/",
            "/analytics/",
            "/manager/orders/",
            "/manager/products/",
            "/manager/supplies/",
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_client_sees_only_own_orders(self):
        self.client.login(username="client1", password="pass12345")
        response = self.client.get(reverse("order_detail", args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("order_detail", args=[self.other_order.pk]))
        self.assertEqual(response.status_code, 302)

    def test_registration_creates_client_and_customer_profile(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newclient",
                "first_name": "Новый",
                "last_name": "Клиент",
                "email": "new@example.com",
                "phone": "+79991234567",
                "password1": "VeryStrongPass123!",
                "password2": "VeryStrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="newclient")
        self.assertEqual(user.role, User.Role.CLIENT)
        self.assertTrue(Customer.objects.filter(user=user).exists())


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Цветы", slug="flowers")
        cls.product = Product.objects.create(
            category=cls.category,
            name="Тюльпан",
            sku="TUL-001",
            price=Decimal("120.00"),
            cost_price=Decimal("60.00"),
            stock_quantity=50,
        )
        cls.client_user = User.objects.create_user(
            username="api_client", password="pass12345", role=User.Role.CLIENT
        )
        cls.manager = User.objects.create_user(
            username="api_manager", password="pass12345", role=User.Role.MANAGER
        )
        cls.customer = Customer.objects.create(
            user=cls.client_user, full_name="API Клиент"
        )

    def test_public_catalog_api_is_read_only(self):
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["count"], 1)

        response = self.client.post(
            "/api/products/",
            {"name": "Взлом", "sku": "HACK-1", "price": 1, "category": self.category.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_client_can_create_order_via_api(self):
        self.client.login(username="api_client", password="pass12345")
        response = self.client.post(
            "/api/orders/",
            {
                "items": [{"product": self.product.pk, "quantity": 2}],
                "delivery_address": "Москва, ул. API, 1",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["customer"], self.customer.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 48)

    def test_manager_orders_are_hidden_from_client(self):
        order = create_order(
            customer=self.customer,
            items=[(self.product.id, 1)],
        )
        self.client.login(username="api_client", password="pass12345")
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

        self.client.logout()
        self.client.login(username="api_manager", password="pass12345")
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_analytics_api_requires_manager(self):
        self.client.login(username="api_client", password="pass12345")
        self.assertEqual(self.client.get("/api/analytics/metrics/").status_code, 403)
        self.client.logout()
        self.client.login(username="api_manager", password="pass12345")
        # Бэктест ещё не запускался — API корректно отвечает 404.
        self.assertEqual(self.client.get("/api/analytics/metrics/").status_code, 404)
