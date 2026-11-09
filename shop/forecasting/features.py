"""Построение признаков временного ряда для прогнозной модели."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


def holiday_feature_frame(
    dates: pd.DatetimeIndex,
    holidays: list[dict],
    *,
    include_promo: bool = False,
    promo: np.ndarray | None = None,
) -> pd.DataFrame:
    """Собирает матрицу признаков: тренд, день недели, Fourier, праздники."""

    dates = pd.DatetimeIndex(dates)
    day_of_year = dates.dayofyear.to_numpy(dtype=float)
    # Абсолютный тренд: одинаковый отсчёт для обучения и прогноза,
    # чтобы признак не «сбрасывался» в ноль на тестовом периоде.
    trend_days = (dates - pd.Timestamp("2020-01-01")).days.to_numpy(dtype=float)

    data: dict[str, np.ndarray] = {
        # Тренд в годах — небольшой масштаб, удобный для регуляризации.
        "trend": trend_days / 365.25,
    }

    # День недели: понедельник — базовая категория.
    weekday = dates.dayofweek.to_numpy()
    for day in range(1, 7):
        data[f"dow_{day}"] = (weekday == day).astype(float)

    # Годовая сезонность через ряды Фурье (3 гармоники).
    for harmonic in range(1, 4):
        angle = 2 * np.pi * harmonic * day_of_year / 365.25
        data[f"sin_{harmonic}"] = np.sin(angle)
        data[f"cos_{harmonic}"] = np.cos(angle)

    # Праздничные признаки: плавный разгон, сам день и короткий хвост.
    for holiday in holidays:
        code = holiday["code"]
        month = int(holiday["month"])
        day = int(holiday["day"])
        window = int(holiday.get("window", 10))
        pre = np.zeros(len(dates), dtype=float)
        post = np.zeros(len(dates), dtype=float)
        exact = np.zeros(len(dates), dtype=float)

        for i, timestamp in enumerate(dates):
            current = timestamp.date()
            try:
                holiday_date = date(current.year, month, day)
            except ValueError:
                continue
            delta = (holiday_date - current).days
            if 0 <= delta <= window:
                pre[i] = (1 - delta / (window + 1)) ** 1.35
            elif -2 <= delta < 0:
                post[i] = 0.18
            if delta == 0:
                exact[i] = 1.0

        data[f"pre_{code}"] = pre
        data[f"post_{code}"] = post
        data[f"day_{code}"] = exact

    if include_promo:
        data["promo"] = (
            np.asarray(promo, dtype=float)
            if promo is not None
            else np.zeros(len(dates), dtype=float)
        )

    return pd.DataFrame(data, index=dates)


def holiday_name_for_date(current_date: date, holidays: list[dict]) -> tuple[bool, str]:
    """Определяет, попадает ли дата в праздничное окно, и возвращает название."""

    best_distance = 10_000
    best_name = ""
    is_peak = False
    for holiday in holidays:
        try:
            holiday_date = date(current_date.year, holiday["month"], holiday["day"])
        except ValueError:
            continue
        delta = (holiday_date - current_date).days
        window = int(holiday.get("window", 10))
        if 0 <= delta <= window or -1 <= delta < 0:
            is_peak = True
            if abs(delta) < best_distance:
                best_distance = abs(delta)
                best_name = holiday.get("short_name") or holiday.get("name", "")
    return is_peak, best_name
