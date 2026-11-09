"""Импортирует внешний реальный датасет продаж цветочного магазина."""

from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from shop.models import RealMarketRecord


class Command(BaseCommand):
    help = "Импортирует CashierData.csv в таблицу RealMarketRecord"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(Path(settings.BASE_DIR) / "data" / "real" / "cashier_data.csv"),
            help="Путь к CSV-файлу (разделитель ;, десятичная запятая)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Файл не найден: {path}"))
            return

        frame = pd.read_csv(path, sep=";", decimal=",")
        frame["Date"] = pd.to_datetime(frame["Date"]).dt.date
        records = []
        for row in frame.itertuples(index=False):
            records.append(
                RealMarketRecord(
                    date=row.Date,
                    cut_flowers=float(0 if pd.isna(row.CutFlowers) else row.CutFlowers),
                    pot_own=float(0 if pd.isna(row.PotOwn) else row.PotOwn),
                    pot_purchased=float(
                        0 if pd.isna(row.PotPurchased) else row.PotPurchased
                    ),
                    wholesale=float(0 if pd.isna(row.Wholesale) else row.Wholesale),
                    fruits_vegs=float(0 if pd.isna(row.FruitsVegs) else row.FruitsVegs),
                    commodity=float(0 if pd.isna(row.Commodity) else row.Commodity),
                    mean_temp=float(row.mean_temp) if pd.notna(row.mean_temp) else None,
                    mean_humidity=(
                        float(row.mean_humid) if pd.notna(row.mean_humid) else None
                    ),
                    public_holiday=str(getattr(row, "public_holiday", "") or ""),
                    school_holiday=str(getattr(row, "school_holiday", "") or ""),
                    source=path.name,
                )
            )

        RealMarketRecord.objects.all().delete()
        RealMarketRecord.objects.bulk_create(records, batch_size=500)
        self.stdout.write(
            self.style.SUCCESS(
                f"Импортировано {len(records)} реальных наблюдений "
                f"({frame['Date'].min()}–{frame['Date'].max()})."
            )
        )
