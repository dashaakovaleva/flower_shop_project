"""Метрики качества прогноза, ошибки I/II рода и сравнение с реальными данными."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, pearsonr


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return float(numerator / denominator) if denominator else default


def regression_metrics(
    actual,
    predicted,
    lower=None,
    upper=None,
) -> dict:
    """MAE, RMSE, MAPE, WAPE, смещение и покрытие интервала."""

    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if actual.size == 0:
        return {
            "n_obs": 0,
            "mae": 0.0,
            "rmse": 0.0,
            "mape": 0.0,
            "wape": 0.0,
            "bias_pct": 0.0,
            "coverage_pct": 0.0,
            "actual_mean": 0.0,
            "predicted_mean": 0.0,
        }

    error = predicted - actual
    abs_error = np.abs(error)
    mae = float(np.mean(abs_error))
    rmse = float(np.sqrt(np.mean(error**2)))
    mape = float(np.mean(abs_error / np.maximum(actual, 1.0)) * 100)
    wape = _safe_div(float(np.sum(abs_error)) * 100, float(np.sum(actual)))
    bias_pct = _safe_div(float(np.mean(error)) * 100, float(np.mean(actual)))

    coverage = 0.0
    if lower is not None and upper is not None:
        lower = np.asarray(lower, dtype=float)
        upper = np.asarray(upper, dtype=float)
        coverage = float(np.mean((actual >= lower) & (actual <= upper)) * 100)

    return {
        "n_obs": int(actual.size),
        "mae": round(mae, 3),
        "rmse": round(rmse, 3),
        "mape": round(mape, 3),
        "wape": round(wape, 3),
        "bias_pct": round(bias_pct, 3),
        "coverage_pct": round(coverage, 3),
        "actual_mean": round(float(np.mean(actual)), 3),
        "predicted_mean": round(float(np.mean(predicted)), 3),
    }


def segment_metrics(frame: pd.DataFrame) -> list[dict]:
    """Считает метрики отдельно для всех, обычных и пиковых дней."""

    if frame.empty:
        return []

    segments = [
        ("all", frame),
        ("normal", frame[~frame["is_peak"].astype(bool)]),
        ("peak", frame[frame["is_peak"].astype(bool)]),
    ]
    result = []
    for segment, subset in segments:
        if subset.empty:
            continue
        metrics = regression_metrics(
            subset["actual"],
            subset["predicted"],
            subset["lower"],
            subset["upper"],
        )
        metrics["segment"] = segment
        result.append(metrics)
    return result


def _confusion_rates(tp: int, fp: int, fn: int, tn: int) -> dict:
    total = tp + fp + fn + tn
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return {
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
        "total": int(total),
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1": round(f1 * 100, 2),
        "accuracy": round(_safe_div(tp + tn, total) * 100, 2),
        # Ошибка I рода — ложная тревога, ошибка II рода — пропущенный пик.
        "type_i_error": int(fp),
        "type_ii_error": int(fn),
        "type_i_rate": round(_safe_div(fp, fp + tn) * 100, 2),
        "type_ii_rate": round(_safe_div(fn, fn + tp) * 100, 2),
    }


def high_demand_confusion(frame: pd.DataFrame, train_values) -> dict:
    """Классификация «высокий спрос / обычный день» по 80-му перцентилю.

    Если передан обучающий DataFrame с колонками ``product_id`` и ``quantity``,
    порог считается отдельно для каждого товара. Это корректнее глобального
    порога: у разных букетов разный масштаб спроса.
    """

    if frame.empty:
        return _confusion_rates(0, 0, 0, 0)

    actual = frame["actual"].to_numpy(dtype=float)
    predicted = frame["predicted"].to_numpy(dtype=float)

    if isinstance(train_values, pd.DataFrame) and {"product_id", "quantity"} <= set(
        train_values.columns
    ):
        thresholds = (
            train_values.groupby("product_id")["quantity"]
            .quantile(0.80)
            .to_dict()
        )
        default_threshold = float(train_values["quantity"].quantile(0.80))
        product_ids = frame["product_id"].to_numpy()
        threshold = np.array(
            [float(thresholds.get(int(pid), default_threshold)) for pid in product_ids]
        )
        threshold_label = "80-й перцентиль обучения по каждому товару"
    else:
        scalar = float(np.quantile(np.asarray(train_values, dtype=float), 0.80))
        threshold = np.full(len(frame), scalar)
        threshold_label = "80-й перцентиль обучения (общий)"

    actual_high = actual > threshold
    predicted_high = predicted > threshold

    tp = int(np.sum(actual_high & predicted_high))
    fp = int(np.sum(~actual_high & predicted_high))
    fn = int(np.sum(actual_high & ~predicted_high))
    tn = int(np.sum(~actual_high & ~predicted_high))
    result = _confusion_rates(tp, fp, fn, tn)
    result["threshold"] = round(float(np.mean(threshold)), 3)
    result["threshold_label"] = threshold_label
    result["definition"] = (
        "Высокий спрос = факт или прогноз выше 80-го перцентиля обучающей выборки"
    )
    return result


def weekly_stockout_confusion(
    frame: pd.DataFrame,
    train_frame: pd.DataFrame,
    *,
    horizon: int = 7,
    safety_rate: float = 0.15,
    stock_quantile: float = 0.90,
) -> dict:
    """Ошибки I/II рода для сигналов «товара не хватит на 7 дней».

    Имитируем текущий запас как 90-й перцентиль семидневного спроса
    в обучающем периоде (высокий, но не идеальный уровень сервиса).
    Тревога модели — прогноз с запасом выше остатка.
    Фактический дефицит — фактический спрос выше остатка.
    """

    if frame.empty or train_frame.empty:
        return _confusion_rates(0, 0, 0, 0)

    train = train_frame.copy()
    train["date"] = pd.to_datetime(train["date"])
    train = train.sort_values(["product_id", "date"])

    stock_by_product: dict[int, float] = {}
    for product_id, group in train.groupby("product_id"):
        rolling = group["quantity"].rolling(horizon, min_periods=1).sum()
        stock_by_product[int(product_id)] = float(
            max(1.0, np.quantile(rolling.dropna(), stock_quantile))
        )

    test = frame.copy()
    test["date"] = pd.to_datetime(test["date"])
    test = test.sort_values(["product_id", "date"])

    tp = fp = fn = tn = 0
    windows: list[dict] = []
    for product_id, group in test.groupby("product_id"):
        product_id = int(product_id)
        stock = stock_by_product.get(product_id)
        if stock is None:
            continue
        group = group.reset_index(drop=True)
        for start in range(0, len(group) - horizon + 1, horizon):
            window = group.iloc[start : start + horizon]
            actual_sum = float(window["actual"].sum())
            predicted_sum = float(window["predicted"].sum())
            actual_shortage = actual_sum > stock
            alarm = predicted_sum * (1 + safety_rate) > stock
            if alarm and actual_shortage:
                tp += 1
            elif alarm and not actual_shortage:
                fp += 1
            elif not alarm and actual_shortage:
                fn += 1
            else:
                tn += 1
            windows.append(
                {
                    "product_id": product_id,
                    "stock": round(stock, 2),
                    "actual": round(actual_sum, 2),
                    "predicted": round(predicted_sum, 2),
                    "alarm": alarm,
                    "shortage": actual_shortage,
                }
            )

    result = _confusion_rates(tp, fp, fn, tn)
    result["definition"] = (
        "Тревога: прогноз спроса с запасом 15% выше имитируемого остатка; "
        "дефицит: фактический спрос выше остатка"
    )
    result["horizon"] = horizon
    result["stock_quantile"] = stock_quantile
    result["windows"] = windows[:200]
    return result


def _profile(frame: pd.DataFrame, by: str) -> pd.Series:
    values = frame.groupby(by)["quantity"].mean()
    mean = values.mean()
    return (values / mean) if mean else values


def comparison_stats(synthetic: pd.DataFrame, real: pd.DataFrame) -> dict:
    """Сравнивает синтетические и реальные продажи в нормированном масштабе."""

    if synthetic.empty or real.empty:
        return {"available": False}

    syn = synthetic.copy()
    real = real.copy()
    syn["date"] = pd.to_datetime(syn["date"])
    real["date"] = pd.to_datetime(real["date"])
    real = real[real["quantity"] > 0].copy()
    if real.empty:
        return {"available": False}

    syn_values = syn["quantity"].to_numpy(dtype=float)
    real_values = real["quantity"].to_numpy(dtype=float)

    syn_norm = syn_values / np.mean(syn_values)
    real_norm = real_values / np.mean(real_values)
    ks = ks_2samp(syn_norm, real_norm)

    syn["weekday"] = syn["date"].dt.dayofweek
    real["weekday"] = real["date"].dt.dayofweek
    syn["month"] = syn["date"].dt.month
    real["month"] = real["date"].dt.month

    weekly_syn = _profile(syn, "weekday")
    weekly_real = _profile(real, "weekday")
    monthly_syn = _profile(syn, "month")
    monthly_real = _profile(real, "month")

    aligned_weekly = pd.concat(
        [weekly_syn.rename("synthetic"), weekly_real.rename("real")], axis=1
    ).fillna(1.0)
    aligned_monthly = pd.concat(
        [monthly_syn.rename("synthetic"), monthly_real.rename("real")], axis=1
    ).fillna(1.0)

    weekly_corr = (
        float(pearsonr(aligned_weekly["synthetic"], aligned_weekly["real"]).statistic)
        if len(aligned_weekly) > 2
        else 0.0
    )
    monthly_corr = (
        float(pearsonr(aligned_monthly["synthetic"], aligned_monthly["real"]).statistic)
        if len(aligned_monthly) > 2
        else 0.0
    )

    def describe(values: np.ndarray) -> dict:
        return {
            "mean": round(float(np.mean(values)), 2),
            "std": round(float(np.std(values)), 2),
            "cv": round(float(np.std(values) / np.mean(values)), 3),
            "skew": round(float(pd.Series(values).skew()), 3),
            "p10": round(float(np.quantile(values, 0.10)), 2),
            "p50": round(float(np.quantile(values, 0.50)), 2),
            "p90": round(float(np.quantile(values, 0.90)), 2),
            "zero_share": round(float(np.mean(values == 0)), 3),
            "autocorr_lag1": round(float(pd.Series(values).autocorr(1)), 3),
            "autocorr_lag7": round(float(pd.Series(values).autocorr(7)), 3),
        }

    return {
        "available": True,
        "synthetic": describe(syn_values),
        "real": describe(real_values),
        "ks_statistic": round(float(ks.statistic), 4),
        "ks_pvalue": round(float(ks.pvalue), 6),
        "weekly_correlation": round(weekly_corr, 4),
        "monthly_correlation": round(monthly_corr, 4),
        "weekly_synthetic": {int(k): round(float(v), 4) for k, v in weekly_syn.items()},
        "weekly_real": {int(k): round(float(v), 4) for k, v in weekly_real.items()},
        "monthly_synthetic": {int(k): round(float(v), 4) for k, v in monthly_syn.items()},
        "monthly_real": {int(k): round(float(v), 4) for k, v in monthly_real.items()},
        "synthetic_days": int(len(syn)),
        "real_days": int(len(real)),
        "real_start": str(real["date"].min().date()),
        "real_end": str(real["date"].max().date()),
        "interpretation": (
            "Высокая корреляция недельного профиля означает, что синтетика "
            "воспроизводит реальный ритм спроса. Расхождение по KS и CV "
            "объясняется российскими праздничными пиками и разной длиной рядов."
        ),
    }
