"""Создаёт справочники, демо-пользователей и клиентов."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from shop.forecasting.constants import (
    CATEGORIES,
    CUSTOMER_NAMES,
    HOLIDAYS,
    PRODUCT_BLUEPRINTS,
    SUPPLIERS,
)
from shop.models import Category, Customer, PeakDate, Product, Supplier, User


class Command(BaseCommand):
    help = "Заполняет справочники, роли и демонстрационных клиентов"

    @transaction.atomic
    def handle(self, *args, **options):
        categories: dict[str, Category] = {}
        for item in CATEGORIES:
            category, _ = Category.objects.update_or_create(
                name=item["name"],
                defaults={
                    "slug": item["slug"],
                    "description": item["description"],
                    "icon": item["icon"],
                    "accent": item["accent"],
                },
            )
            categories[item["name"]] = category

        created_products = 0
        for blueprint in PRODUCT_BLUEPRINTS:
            product, created = Product.objects.get_or_create(
                sku=blueprint["sku"],
                defaults={
                    "category": categories[blueprint["category"]],
                    "name": blueprint["name"],
                    "description": (
                        f"{blueprint['name']} — товар категории "
                        f"«{blueprint['category']}» цветочного магазина FloraIS."
                    ),
                    "price": Decimal(str(blueprint["price"])),
                    "cost_price": Decimal(str(blueprint["cost_price"])),
                    "stock_quantity": blueprint["stock"],
                    "min_stock": blueprint["min_stock"],
                    "image_emoji": blueprint["emoji"],
                    "is_active": True,
                },
            )
            if not created:
                product.category = categories[blueprint["category"]]
                product.name = blueprint["name"]
                product.price = Decimal(str(blueprint["price"]))
                product.cost_price = Decimal(str(blueprint["cost_price"]))
                product.min_stock = blueprint["min_stock"]
                product.image_emoji = blueprint["emoji"]
                product.is_active = True
                product.save()
            else:
                created_products += 1

        for item in SUPPLIERS:
            Supplier.objects.update_or_create(
                name=item["name"],
                defaults={
                    "contact_person": item["contact_person"],
                    "phone": item["phone"],
                    "email": item["email"],
                    "address": item["address"],
                    "is_active": True,
                },
            )

        for holiday in HOLIDAYS:
            PeakDate.objects.update_or_create(
                month=holiday["month"],
                day=holiday["day"],
                defaults={
                    "name": holiday["name"],
                    "demand_coefficient": Decimal(str(holiday["coefficient"])),
                    "window_days": holiday["window"],
                    "color": holiday["color"],
                    "description": holiday["description"],
                },
            )

        users = [
            {
                "username": "admin",
                "password": "admin123",
                "role": User.Role.ADMIN,
                "first_name": "Дарья",
                "last_name": "Ковалева",
                "email": "admin@florais.local",
                "is_staff": True,
                "is_superuser": True,
            },
            {
                "username": "manager",
                "password": "manager123",
                "role": User.Role.MANAGER,
                "first_name": "Ольга",
                "last_name": "Менеджерова",
                "email": "manager@florais.local",
                "is_staff": True,
                "is_superuser": False,
            },
            {
                "username": "client",
                "password": "client123",
                "role": User.Role.CLIENT,
                "first_name": "Анна",
                "last_name": "Смирнова",
                "email": "client@florais.local",
                "is_staff": False,
                "is_superuser": False,
            },
        ]
        for item in users:
            user, created = User.objects.get_or_create(
                username=item["username"],
                defaults={
                    "role": item["role"],
                    "first_name": item["first_name"],
                    "last_name": item["last_name"],
                    "email": item["email"],
                    "is_staff": item["is_staff"],
                    "is_superuser": item["is_superuser"],
                },
            )
            user.role = item["role"]
            user.first_name = item["first_name"]
            user.last_name = item["last_name"]
            user.email = item["email"]
            user.is_staff = item["is_staff"]
            user.is_superuser = item["is_superuser"]
            if created or not user.has_usable_password():
                user.set_password(item["password"])
            user.save()

        client_user = User.objects.get(username="client")
        Customer.objects.update_or_create(
            user=client_user,
            defaults={
                "customer_type": Customer.CustomerType.PHYSICAL,
                "full_name": "Анна Смирнова",
                "phone": "+7 (900) 100-20-30",
                "email": "client@florais.local",
                "address": "Москва, ул. Цветочная, 8, кв. 14",
            },
        )

        for index, (customer_type, full_name, company_name, inn) in enumerate(CUSTOMER_NAMES):
            lookup = (
                {"full_name": full_name}
                if customer_type == "Физическое лицо"
                else {"company_name": company_name}
            )
            Customer.objects.get_or_create(
                **lookup,
                defaults={
                    "customer_type": (
                        Customer.CustomerType.PHYSICAL
                        if customer_type == "Физическое лицо"
                        else Customer.CustomerType.LEGAL
                    ),
                    "inn": inn,
                    "phone": f"+7 (900) 200-{index:02d}-{index:02d}",
                    "email": f"client{index}@example.ru",
                    "address": "Москва, ул. Примерная, д. 1",
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Справочники готовы: категорий — {len(categories)}, "
                f"товаров — {Product.objects.count()} (создано {created_products}), "
                f"поставщиков — {Supplier.objects.count()}, "
                f"пользователей — {User.objects.count()}, клиентов — {Customer.objects.count()}."
            )
        )
