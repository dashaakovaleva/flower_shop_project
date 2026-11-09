"""Генератор синтетических продаж с недельной, годовой и праздничной сезонностью.

Модель генерации:
    спрос = база × тренд × день_недели × месяц × праздничный_разгон × шум × акция

Первые два года помечаются как train, третий год генерируется отдельным
случайным потоком с изменившимися условиями и используется как отложенная
«реальная» выборка для честной проверки прогноза.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from django.utils import timezone

from .constants import (
    HOLIDAYS,
    MONTH_FACTORS,
    PRODUCT_BLUEPRINTS,
    WEEKDAY_FACTORS,
)


def _holiday_lift(
    current_date: date,
    weights: dict[str, float],
    holiday_scale: float = 1.0,
) -> tuple[float, str, bool]:
    """Возвращает множитель спроса, название праздника и признак пика."""

    best_lift = 1.0
    best_name = ""
    is_peak = False

    for holiday in HOLIDAYS:
        try:
            holiday_date = date(current_date.year, holiday["month"], holiday["day"])
        except ValueError:
            continue
        delta = (holiday_date - current_date).days
        window = holiday["window"]
        weight = float(weights.get(holiday["code"], 0.0))
        if weight <= 0:
            continue

        if 0 <= delta <= window:
            # Плавный разгон: чем ближе праздник, тем сильнее эффект.
            ramp = (1 - delta / (window + 1)) ** 1.35
            lift = 1 + (holiday["coefficient"] * holiday_scale - 1) * weight * ramp
        elif -2 <= delta < 0:
            # Небольшой хвост после праздника.
            lift = 1 + (holiday["coefficient"] * holiday_scale - 1) * weight * 0.18
        else:
            lift = 1.0

        if lift > best_lift:
            best_lift = lift
            best_name = holiday["short_name"]
        if 0 <= delta <= window or -1 <= delta < 0:
            is_peak = True

    return max(1.0, best_lift), best_name, is_peak


def generate_dataset(
    start_date: date,
    end_date: date,
    *,
    dataset: str,
    seed: int,
    demand_scale: float = 1.0,
    holiday_scale: float = 1.0,
    noise: float = 0.16,
    promo_probability: float = 0.012,
    trend_rate: float = 0.04,
    ar_coefficient: float = 0.25,
) -> pd.DataFrame:
    """Генерирует дневные продажи по всем товарам за указанный период."""

    rng = np.random.default_rng(seed)
    dates = pd.date_range(start_date, end_date, freq="D")
    rows: list[dict] = []

    for blueprint in PRODUCT_BLUEPRINTS:
        z_prev = 0.0
        base = float(blueprint["base"]) * demand_scale
        price = float(blueprint["price"])
        weights = blueprint["weights"]

        for index, timestamp in enumerate(dates):
            current_date = timestamp.date()
            weekday_factor = WEEKDAY_FACTORS[current_date.weekday()]
            month_factor = MONTH_FACTORS[current_date.month]
            trend = (1 + trend_rate) ** (index / 365.25)
            holiday_factor, holiday_name, is_peak = _holiday_lift(
                current_date, weights, holiday_scale=holiday_scale
            )

            # AR(1) в логарифмическом масштабе — плавные колебания спроса.
            innovation = rng.normal(0, noise)
            z = ar_coefficient * z_prev + np.sqrt(1 - ar_coefficient**2) * innovation
            z_prev = z
            noise_factor = np.exp(z - 0.5 * noise**2)

            promo = False
            promo_factor = 1.0
            if (
                not is_peak
                and base * weekday_factor > 1.5
                and rng.random() < promo_probability
            ):
                promo = True
                promo_factor = rng.uniform(1.35, 2.1)

            expected = (
                base
                * trend
                * weekday_factor
                * month_factor
                * holiday_factor
                * promo_factor
            )
            quantity = int(max(0, round(expected * noise_factor)))
            revenue = round(quantity * price, 2)

            rows.append(
                {
                    "date": current_date,
                    "sku": blueprint["sku"],
                    "product_name": blueprint["name"],
                    "category": blueprint["category"],
                    "quantity": quantity,
                    "revenue": revenue,
                    "dataset": dataset,
                    "is_peak": is_peak,
                    "holiday_name": holiday_name if is_peak else "",
                    "promo": promo,
                    "expected": round(expected, 2),
                }
            )

    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values(["date", "sku"]).reset_index(drop=True)


def generate_train_and_holdout(today: date | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Формирует 2 года обучения и 365-дневный отложенный год."""

    today = today or timezone.localdate()
    end_date = today - timedelta(days=1)
    holdout_start = end_date - timedelta(days=364)
    train_end = holdout_start - timedelta(days=1)
    train_start = train_end - timedelta(days=729)

    train = generate_dataset(
        train_start,
        train_end,
        dataset="train",
        seed=42,
        demand_scale=1.0,
        holiday_scale=1.0,
        noise=0.16,
        promo_probability=0.012,
    )
    holdout = generate_dataset(
        holdout_start,
        end_date,
        dataset="holdout",
        seed=2026,
        demand_scale=1.06,
        holiday_scale=0.88,
        noise=0.22,
        promo_probability=0.015,
        trend_rate=0.06,
    )

    meta = {
        "train_start": train_start,
        "train_end": train_end,
        "holdout_start": holdout_start,
        "holdout_end": end_date,
        "today": today,
        "train_rows": len(train),
        "holdout_rows": len(holdout),
    }
    return train, holdout, meta


def daily_totals(frame: pd.DataFrame) -> pd.DataFrame:
    """Агрегирует продажи по дням для графиков и сравнения с реальными данными."""

    aggregations = {"quantity": ("quantity", "sum")}
    if "revenue" in frame.columns:
        aggregations["revenue"] = ("revenue", "sum")
    result = (
        frame.groupby("date", as_index=False)
        .agg(**aggregations)
        .sort_values("date")
    )
    return result
