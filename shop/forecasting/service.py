"""Сервис обучения, бэктеста и рабочего прогнозирования спроса."""

from __future__ import annotations

import math
import time
from datetime import timedelta

import numpy as np
import pandas as pd
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from shop.models import (
    Forecast,
    ModelMetric,
    ModelRun,
    PeakDate,
    Product,
    RealMarketRecord,
    Recommendation,
    SalesRecord,
)

from .backends import fit_predict
from .constants import HOLIDAYS
from .metrics import (
    comparison_stats,
    high_demand_confusion,
    segment_metrics,
    weekly_stockout_confusion,
)
from .synthetic import daily_totals


def holiday_definitions() -> list[dict]:
    """Праздники из БД; если справочник пуст — встроенные значения."""

    peaks = list(PeakDate.objects.all())
    if not peaks:
        return HOLIDAYS

    code_by_date = {(h["month"], h["day"]): h["code"] for h in HOLIDAYS}
    result = []
    for peak in peaks:
        result.append(
            {
                "code": code_by_date.get((peak.month, peak.day), f"peak_{peak.month}_{peak.day}"),
                "name": peak.name,
                "short_name": peak.name.split("—")[0].strip(),
                "month": peak.month,
                "day": peak.day,
                "coefficient": float(peak.demand_coefficient),
                "window": peak.window_days,
                "color": peak.color,
            }
        )
    return result


def _load_sales(
    dataset: str | None = None,
    *,
    start=None,
    end=None,
    product_id: int | None = None,
) -> pd.DataFrame:
    queryset = SalesRecord.objects.select_related("product").all()
    if dataset:
        queryset = queryset.filter(dataset=dataset)
    if start:
        queryset = queryset.filter(date__gte=start)
    if end:
        queryset = queryset.filter(date__lte=end)
    if product_id:
        queryset = queryset.filter(product_id=product_id)

    rows = list(
        queryset.values(
            "product_id",
            "product__name",
            "product__sku",
            "date",
            "quantity",
            "is_peak",
            "holiday_name",
            "promo",
        )
    )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.sort_values(["product_id", "date"]).reset_index(drop=True)
    return frame


def _to_builtin(value):
    """Рекурсивно приводит numpy-типы к JSON-совместимым Python-типам."""

    if isinstance(value, dict):
        return {key: _to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_builtin(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _model_label(model_name: str) -> str:
    return {
        "sarimax": "SARIMAX(1,0,1)(1,0,1,7) + экзогенные признаки",
        "regression": "Сезонная регрессия (Fourier + праздничные лаги)",
        "auto": "SARIMAX с автоматическим fallback",
    }.get(model_name, model_name)


def _real_reference_frame() -> pd.DataFrame:
    rows = list(RealMarketRecord.objects.values("date", "cut_flowers"))
    if not rows:
        return pd.DataFrame(columns=["date", "quantity"])
    frame = pd.DataFrame(rows).rename(columns={"cut_flowers": "quantity"})
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values("date").reset_index(drop=True)


def run_backtest(model_name: str | None = None, *, horizon: int = 365) -> ModelRun:
    """Обучает модель на 2 годах синтетики и проверяет на 3-м годе."""

    model_name = model_name or getattr(settings, "FORECAST_MODEL", "sarimax")
    train = _load_sales(SalesRecord.Dataset.TRAIN)
    holdout = _load_sales(SalesRecord.Dataset.HOLDOUT)
    if train.empty or holdout.empty:
        raise RuntimeError(
            "Нет данных для бэктеста. Выполните: python manage.py generate_sales"
        )

    start_time = time.perf_counter()
    run = ModelRun.objects.create(
        kind=ModelRun.Kind.BACKTEST,
        model_name=_model_label(model_name),
        status=ModelRun.Status.RUNNING,
        train_start=train["date"].min().date(),
        train_end=train["date"].max().date(),
        test_start=holdout["date"].min().date(),
        test_end=holdout["date"].max().date(),
        horizon_days=min(horizon, holdout["date"].nunique()),
        params={"requested_model": model_name, "safety_rate": settings.FORECAST_SAFETY_STOCK_RATE},
    )

    holidays = holiday_definitions()
    frames: list[pd.DataFrame] = []
    fallback_count = 0
    used_models: set[str] = set()
    forecast_objects: list[Forecast] = []

    try:
        for product_id, train_group in train.groupby("product_id"):
            test_group = holdout[holdout["product_id"] == product_id].sort_values("date")
            if test_group.empty or len(train_group) < 21:
                continue

            train_group = train_group.sort_values("date")
            prediction = fit_predict(
                pd.DatetimeIndex(train_group["date"]),
                train_group["quantity"].to_numpy(dtype=float),
                pd.DatetimeIndex(test_group["date"]),
                holidays,
                model_name=model_name,
                promo_train=train_group["promo"].astype(float).to_numpy(),
                promo_pred=np.zeros(len(test_group), dtype=float),
            )
            if prediction.fallback:
                fallback_count += 1
            used_models.add(prediction.model_name)

            frame = pd.DataFrame(
                {
                    "product_id": int(product_id),
                    "product_name": test_group["product__name"].iloc[0],
                    "date": test_group["date"].to_numpy(),
                    "actual": test_group["quantity"].to_numpy(dtype=float),
                    "predicted": prediction.mean,
                    "lower": prediction.lower,
                    "upper": prediction.upper,
                    "is_peak": test_group["is_peak"].astype(bool).to_numpy(),
                    "holiday_name": test_group["holiday_name"].to_numpy(),
                }
            )
            frames.append(frame)

            for row in frame.itertuples(index=False):
                forecast_objects.append(
                    Forecast(
                        run=run,
                        product_id=int(row.product_id),
                        date=pd.Timestamp(row.date).date(),
                        predicted_quantity=round(float(row.predicted), 3),
                        lower_bound=round(float(row.lower), 3),
                        upper_bound=round(float(row.upper), 3),
                        actual_quantity=float(row.actual),
                        is_peak=bool(row.is_peak),
                        holiday_name=str(row.holiday_name or ""),
                    )
                )

        if not frames:
            raise RuntimeError("Не удалось построить прогноз ни для одного товара.")

        # Сохраняем точки прогноза пакетами, чтобы не перегружать SQLite.
        Forecast.objects.bulk_create(forecast_objects, batch_size=1000)

        all_predictions = pd.concat(frames, ignore_index=True)
        metrics = segment_metrics(all_predictions)
        demand_confusion = high_demand_confusion(all_predictions, train)
        stockout_confusion = weekly_stockout_confusion(
            all_predictions,
            train,
            horizon=7,
            safety_rate=settings.FORECAST_SAFETY_STOCK_RATE,
        )

        real_reference = _real_reference_frame()
        comparison = comparison_stats(daily_totals(train), real_reference)

        duration = time.perf_counter() - start_time
        summary = {
            "duration_seconds": round(duration, 2),
            "products": int(all_predictions["product_id"].nunique()),
            "forecast_points": int(len(all_predictions)),
            "requested_model": model_name,
            "used_models": sorted(used_models),
            "fallback_products": fallback_count,
            "safety_rate": settings.FORECAST_SAFETY_STOCK_RATE,
            "demand_confusion": demand_confusion,
            "stockout_confusion": {
                key: value
                for key, value in stockout_confusion.items()
                if key != "windows"
            },
            "comparison": comparison,
            "segment_metrics": {item["segment"]: item for item in metrics},
            "train_days": int(train["date"].nunique()),
            "test_days": int(holdout["date"].nunique()),
            "train_quantity_mean": round(float(train["quantity"].mean()), 3),
            "test_quantity_mean": round(float(holdout["quantity"].mean()), 3),
        }

        with transaction.atomic():
            for item in metrics:
                ModelMetric.objects.create(
                    run=run,
                    segment=item["segment"],
                    n_obs=item["n_obs"],
                    mae=item["mae"],
                    rmse=item["rmse"],
                    mape=item["mape"],
                    wape=item["wape"],
                    bias_pct=item["bias_pct"],
                    coverage_pct=item["coverage_pct"],
                    actual_mean=item["actual_mean"],
                    predicted_mean=item["predicted_mean"],
                )
            run.status = ModelRun.Status.COMPLETED
            run.summary = _to_builtin(summary)
            run.save(update_fields=["status", "summary"])

    except Exception as exc:  # noqa: BLE001
        run.status = ModelRun.Status.FAILED
        run.error_message = f"{type(exc).__name__}: {exc}"
        run.summary = {"duration_seconds": round(time.perf_counter() - start_time, 2)}
        run.save(update_fields=["status", "error_message", "summary"])
        raise

    return run


def run_operational_forecast(
    *, horizon: int | None = None, model_name: str | None = None
) -> ModelRun:
    """Строит рабочий прогноз на 7 дней и рекомендации по дозакупке."""

    horizon = horizon or getattr(settings, "FORECAST_HORIZON_DAYS", 7)
    model_name = model_name or getattr(settings, "FORECAST_MODEL", "sarimax")
    today = timezone.localdate()
    history_end = today - timedelta(days=1)

    history = _load_sales(end=history_end)
    if history.empty:
        raise RuntimeError("Нет истории продаж. Выполните: python manage.py generate_sales")

    start_time = time.perf_counter()
    run = ModelRun.objects.create(
        kind=ModelRun.Kind.OPERATIONAL,
        model_name=_model_label(model_name),
        status=ModelRun.Status.RUNNING,
        train_start=history["date"].min().date(),
        train_end=history_end,
        horizon_days=horizon,
        params={
            "requested_model": model_name,
            "safety_rate": settings.FORECAST_SAFETY_STOCK_RATE,
        },
    )

    holidays = holiday_definitions()
    forecast_dates = pd.date_range(today + timedelta(days=1), periods=horizon, freq="D")
    products = list(Product.objects.filter(is_active=True).order_by("name"))
    forecasts: list[Forecast] = []
    recommendations: list[Recommendation] = []
    fallback_count = 0
    used_models: set[str] = set()
    peak_by_date = {}

    for holiday in holidays:
        for year in {today.year, today.year + 1}:
            try:
                peak_date = pd.Timestamp(year=year, month=holiday["month"], day=holiday["day"]).date()
            except ValueError:
                continue
            if forecast_dates[0].date() <= peak_date <= forecast_dates[-1].date():
                peak_by_date[peak_date] = holiday.get("short_name") or holiday["name"]
            # Разгон до праздника тоже считаем пиковым окном.
            for offset in range(1, int(holiday.get("window", 10)) + 1):
                ramp_date = peak_date - timedelta(days=offset)
                if forecast_dates[0].date() <= ramp_date <= forecast_dates[-1].date():
                    peak_by_date.setdefault(
                        ramp_date, f"разгон: {holiday.get('short_name') or holiday['name']}"
                    )

    for product in products:
        product_history = history[history["product_id"] == product.id].sort_values("date")
        if product_history.empty:
            continue
        try:
            prediction = fit_predict(
                pd.DatetimeIndex(product_history["date"]),
                product_history["quantity"].to_numpy(dtype=float),
                forecast_dates,
                holidays,
                model_name=model_name,
                promo_train=product_history["promo"].astype(float).to_numpy(),
                promo_pred=np.zeros(len(forecast_dates), dtype=float),
            )
        except Exception:  # noqa: BLE001
            continue
        if prediction.fallback:
            fallback_count += 1
        used_models.add(prediction.model_name)

        for offset, timestamp in enumerate(forecast_dates):
            forecast_date = timestamp.date()
            forecasts.append(
                Forecast(
                    run=run,
                    product=product,
                    date=forecast_date,
                    predicted_quantity=round(float(prediction.mean[offset]), 3),
                    lower_bound=round(float(prediction.lower[offset]), 3),
                    upper_bound=round(float(prediction.upper[offset]), 3),
                    is_peak=forecast_date in peak_by_date,
                    holiday_name=peak_by_date.get(forecast_date, ""),
                )
            )

        demand = float(np.sum(prediction.mean))
        safety = math.ceil(demand * settings.FORECAST_SAFETY_STOCK_RATE)
        required = demand + safety
        purchase = max(0, math.ceil(required - product.stock_quantity))
        if purchase <= 0:
            continue

        coverage = product.stock_quantity / required if required else 1.0
        if coverage < 0.5:
            priority = Recommendation.Priority.CRITICAL
        elif coverage < 0.75:
            priority = Recommendation.Priority.HIGH
        elif coverage < 0.95:
            priority = Recommendation.Priority.MEDIUM
        else:
            priority = Recommendation.Priority.LOW

        holiday_note = ""
        for holiday in holidays:
            peak_date = holiday["month"], holiday["day"]
            for year in {today.year, today.year + 1}:
                try:
                    candidate = pd.Timestamp(year=year, month=peak_date[0], day=peak_date[1]).date()
                except ValueError:
                    continue
                delta = (candidate - today).days
                if 0 <= delta <= 21:
                    holiday_note = (
                        f" Ближайший пик: {holiday.get('short_name') or holiday['name']} "
                        f"через {delta} дн."
                    )
                    break
            if holiday_note:
                break

        recommendations.append(
            Recommendation(
                run=run,
                product=product,
                horizon_days=horizon,
                forecast_demand=round(demand, 3),
                current_stock=product.stock_quantity,
                safety_stock=float(safety),
                required_stock=round(required, 3),
                purchase_quantity=purchase,
                priority=priority,
                reason=(
                    f"Прогноз спроса на {horizon} дн. — {demand:.0f} шт., "
                    f"остаток — {product.stock_quantity} шт., страховой запас "
                    f"{settings.FORECAST_SAFETY_STOCK_RATE * 100:.0f}% — {safety} шт. "
                    f"Рекомендуется закупить {purchase} шт.{holiday_note}"
                ),
            )
        )

    Forecast.objects.bulk_create(forecasts, batch_size=1000)
    Recommendation.objects.bulk_create(recommendations, batch_size=500)

    duration = time.perf_counter() - start_time
    critical = sum(1 for r in recommendations if r.priority == Recommendation.Priority.CRITICAL)
    high = sum(1 for r in recommendations if r.priority == Recommendation.Priority.HIGH)
    nearest_peak = None
    peak_candidates = []
    for holiday in holidays:
        try:
            candidate = pd.Timestamp(
                year=today.year, month=holiday["month"], day=holiday["day"]
            ).date()
        except ValueError:
            continue
        if candidate < today:
            candidate = pd.Timestamp(
                year=today.year + 1, month=holiday["month"], day=holiday["day"]
            ).date()
        peak_candidates.append(
            {
                "name": holiday.get("short_name") or holiday["name"],
                "date": str(candidate),
                "days_until": (candidate - today).days,
            }
        )
    if peak_candidates:
        nearest_peak = min(peak_candidates, key=lambda item: item["days_until"])

    run.status = ModelRun.Status.COMPLETED
    run.summary = _to_builtin(
        {
            "duration_seconds": round(duration, 2),
            "products": len(products),
            "forecast_points": len(forecasts),
            "recommendations": len(recommendations),
            "critical": critical,
            "high": high,
            "total_purchase_units": int(sum(r.purchase_quantity for r in recommendations)),
            "used_models": sorted(used_models),
            "fallback_products": fallback_count,
            "nearest_peak": nearest_peak,
            "horizon": horizon,
            "safety_rate": settings.FORECAST_SAFETY_STOCK_RATE,
        }
    )
    run.save(update_fields=["status", "summary"])
    return run


def latest_run(kind: str):
    return ModelRun.objects.filter(kind=kind, status=ModelRun.Status.COMPLETED).first()
