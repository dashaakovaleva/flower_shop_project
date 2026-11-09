"""Генерирует синтетические продажи за 2 года и отложенный 3-й год."""

from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from shop.forecasting.synthetic import daily_totals, generate_train_and_holdout
from shop.models import Product, SalesRecord


class Command(BaseCommand):
    help = "Генерирует синтетические продажи: 2 года обучения + 1 отложенный год"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-files",
            action="store_true",
            help="Не сохранять CSV-файлы в data/",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        train, holdout, meta = generate_train_and_holdout()
        products = {product.sku: product for product in Product.objects.all()}
        missing = set(train["sku"].unique()) - set(products)
        if missing:
            self.stderr.write(
                self.style.ERROR(
                    "Сначала выполните seed_reference. Не найдены артикулы: "
                    + ", ".join(sorted(missing))
                )
            )
            return

        SalesRecord.objects.filter(
            dataset__in=[SalesRecord.Dataset.TRAIN, SalesRecord.Dataset.HOLDOUT]
        ).delete()

        def build_objects(frame: pd.DataFrame, dataset: str):
            objects = []
            for row in frame.itertuples(index=False):
                product = products[row.sku]
                objects.append(
                    SalesRecord(
                        product=product,
                        date=row.date.date(),
                        quantity=int(row.quantity),
                        revenue=row.revenue,
                        dataset=dataset,
                        is_peak=bool(row.is_peak),
                        holiday_name=str(row.holiday_name or ""),
                        promo=bool(row.promo),
                    )
                )
            return objects

        SalesRecord.objects.bulk_create(
            build_objects(train, SalesRecord.Dataset.TRAIN), batch_size=1000
        )
        SalesRecord.objects.bulk_create(
            build_objects(holdout, SalesRecord.Dataset.HOLDOUT), batch_size=1000
        )

        # Формируем реалистичные остатки: часть товаров будет в дефиците,
        # чтобы модуль рекомендаций было что показать на защите.
        stock_factors = [0.35, 0.55, 0.75, 0.95, 1.15, 1.45]
        holdout["date"] = pd.to_datetime(holdout["date"])
        recent_start = holdout["date"].max() - pd.Timedelta(days=13)
        recent = holdout[holdout["date"] >= recent_start]
        for index, (sku, group) in enumerate(recent.groupby("sku")):
            product = products.get(sku)
            if not product:
                continue
            daily_mean = float(group["quantity"].mean())
            weekly = max(1.0, daily_mean * 7)
            factor = stock_factors[index % len(stock_factors)]
            product.stock_quantity = max(0, int(round(weekly * factor)))
            product.min_stock = max(3, int(round(weekly * 0.25)))
            product.save(update_fields=["stock_quantity", "min_stock"])

        if not options["no_files"]:
            data_dir = Path(settings.BASE_DIR) / "data"
            data_dir.mkdir(exist_ok=True)
            train.to_csv(data_dir / "synthetic_sales.csv", index=False, encoding="utf-8-sig")
            holdout.to_csv(data_dir / "holdout_sales.csv", index=False, encoding="utf-8-sig")
            daily_totals(train).to_csv(
                data_dir / "synthetic_daily.csv", index=False, encoding="utf-8-sig"
            )
            daily_totals(holdout).to_csv(
                data_dir / "holdout_daily.csv", index=False, encoding="utf-8-sig"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Сгенерировано: "
                f"обучение {meta['train_start']}–{meta['train_end']} "
                f"({meta['train_rows']} строк), "
                f"отложенный год {meta['holdout_start']}–{meta['holdout_end']} "
                f"({meta['holdout_rows']} строк)."
            )
        )
