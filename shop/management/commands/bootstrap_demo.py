"""Одна команда для полной подготовки демонстрационного стенда."""

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Справочники + синтетика + реальные данные + заказы + обучение + прогноз"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-training",
            action="store_true",
            help="Не запускать бэктест и оперативный прогноз",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("1/6 Справочники и пользователи"))
        call_command("seed_reference")

        self.stdout.write(self.style.MIGRATE_HEADING("2/6 Синтетические продажи"))
        call_command("generate_sales")

        real_path = Path(settings.BASE_DIR) / "data" / "real" / "cashier_data.csv"
        if real_path.exists():
            self.stdout.write(self.style.MIGRATE_HEADING("3/6 Реальный датасет"))
            call_command("import_real_data", path=str(real_path))
        else:
            self.stdout.write(self.style.WARNING("3/6 Реальный датасет не найден — пропуск"))

        self.stdout.write(self.style.MIGRATE_HEADING("4/6 Демонстрационные заказы"))
        call_command("create_demo_orders")

        if options["skip_training"]:
            self.stdout.write(
                self.style.WARNING("5/6 и 6/6 Пропущены по флагу --skip-training")
            )
            return

        self.stdout.write(self.style.MIGRATE_HEADING("5/6 Бэктест модели"))
        call_command("train_models")

        self.stdout.write(self.style.MIGRATE_HEADING("6/6 Оперативный прогноз"))
        call_command("make_forecast")

        self.stdout.write(
            self.style.SUCCESS(
                "\nГотово! Запустите сервер: python manage.py runserver\n"
                "Демо-аккаунты: admin/admin123, manager/manager123, client/client123"
            )
        )
