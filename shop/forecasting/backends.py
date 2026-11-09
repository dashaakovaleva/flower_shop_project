"""Прогнозные модели: SARIMAX и сезонная регрессия (fallback)."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .features import holiday_feature_frame


@dataclass
class Prediction:
    mean: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    model_name: str
    fallback: bool = False
    details: dict = field(default_factory=dict)


class SeasonalRegressionModel:
    """Регуляризованная лог-линейная регрессия с сезонными признаками.

    Используется как надёжный fallback, если SARIMAX не сошёлся.
    """

    name = "Сезонная регрессия (Fourier + праздничные лаги)"

    def __init__(self, alpha: float = 1e-3):
        self.alpha = alpha
        self.beta: np.ndarray | None = None
        self.q10 = 0.0
        self.q90 = 0.0
        self.sigma = 0.0
        self._columns: list[str] = []

    def fit(self, dates, y, holidays: list[dict], promo=None):
        X_frame = holiday_feature_frame(dates, holidays, include_promo=True, promo=promo)
        self._columns = list(X_frame.columns)
        X = X_frame.to_numpy(dtype=float)
        X = np.column_stack([np.ones(len(X)), X])
        y_log = np.log1p(np.asarray(y, dtype=float))

        penalty = np.eye(X.shape[1]) * self.alpha
        penalty[0, 0] = 0  # не штрафуем свободный член
        self.beta = np.linalg.solve(X.T @ X + penalty, X.T @ y_log)

        residuals = y_log - X @ self.beta
        self.q10, self.q90 = np.quantile(residuals, [0.10, 0.90])
        self.sigma = float(np.std(residuals))
        return self

    def predict(self, dates, holidays: list[dict], promo=None) -> Prediction:
        if self.beta is None:
            raise RuntimeError("Модель не обучена")
        X_frame = holiday_feature_frame(dates, holidays, include_promo=True, promo=promo)
        X_frame = X_frame.reindex(columns=self._columns, fill_value=0.0)
        X = np.column_stack([np.ones(len(X_frame)), X_frame.to_numpy(dtype=float)])
        pred_log = X @ self.beta
        mean = np.expm1(pred_log)
        lower = np.expm1(pred_log + self.q10)
        upper = np.expm1(pred_log + self.q90)
        mean = np.clip(mean, 0, None)
        lower = np.clip(lower, 0, None)
        upper = np.clip(upper, 0, None)
        return Prediction(
            mean=mean,
            lower=np.minimum(lower, mean),
            upper=np.maximum(upper, mean),
            model_name=self.name,
            details={"residual_sigma": round(self.sigma, 4), "alpha": self.alpha},
        )


class SarimaxModel:
    """SARIMAX(1,0,1)(1,0,1,7) с экзогенными сезонными признаками.

    Дневная сезонность дополнительно описывается дамми дня недели,
    годовая — рядами Фурье, праздничная — ramp-признаками.
    """

    name = "SARIMAX(1,0,1)(1,0,1,7) + экзогенные признаки"

    def __init__(self, order=(1, 0, 1), seasonal_order=(1, 0, 1, 7)):
        self.order = order
        self.seasonal_order = seasonal_order
        self.result = None
        self.q10 = 0.0
        self.q90 = 0.0
        self.sigma = 0.0
        self._columns: list[str] = []
        self._train_len = 0

    def fit(self, dates, y, holidays: list[dict], promo=None):
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        X_frame = holiday_feature_frame(dates, holidays, include_promo=True, promo=promo)
        self._columns = list(X_frame.columns)
        X = X_frame.to_numpy(dtype=float)
        y_log = np.log1p(np.asarray(y, dtype=float))
        self._train_len = len(y_log)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = SARIMAX(
                y_log,
                exog=X,
                order=self.order,
                seasonal_order=self.seasonal_order,
                trend="c",
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            self.result = model.fit(disp=False, maxiter=120, low_memory=True)

        fitted = np.asarray(self.result.fittedvalues, dtype=float)
        residuals = y_log - fitted
        residuals = residuals[np.isfinite(residuals)]
        self.q10, self.q90 = np.quantile(residuals, [0.10, 0.90])
        self.sigma = float(np.std(residuals))
        return self

    def predict(self, dates, holidays: list[dict], promo=None) -> Prediction:
        if self.result is None:
            raise RuntimeError("Модель не обучена")
        dates = pd.DatetimeIndex(dates)
        X_frame = holiday_feature_frame(dates, holidays, include_promo=True, promo=promo)
        X_frame = X_frame.reindex(columns=self._columns, fill_value=0.0)
        X = X_frame.to_numpy(dtype=float)
        if len(X) == 0:
            empty = np.array([], dtype=float)
            return Prediction(empty, empty, empty, self.name)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            forecast = self.result.get_forecast(steps=len(X), exog=X)
            pred_log = np.asarray(forecast.predicted_mean, dtype=float)
            conf = np.asarray(forecast.conf_int(alpha=0.2), dtype=float)

        mean = np.expm1(pred_log)
        if conf.shape == (len(pred_log), 2) and np.isfinite(conf).all():
            lower = np.expm1(conf[:, 0])
            upper = np.expm1(conf[:, 1])
        else:
            # Часть ковариационных оценок statsmodels может быть неопределена
            # (несошедшаяся оптимизация). Тогда используем эмпирические
            # квантили остатков — интервал остаётся содержательным.
            lower = np.expm1(pred_log + self.q10)
            upper = np.expm1(pred_log + self.q90)
        mean = np.clip(mean, 0, None)
        lower = np.clip(lower, 0, None)
        upper = np.clip(upper, 0, None)
        mean = np.nan_to_num(mean, nan=0.0, posinf=0.0, neginf=0.0)
        lower = np.nan_to_num(lower, nan=0.0, posinf=0.0, neginf=0.0)
        upper = np.nan_to_num(upper, nan=0.0, posinf=0.0, neginf=0.0)
        return Prediction(
            mean=mean,
            lower=np.minimum(lower, mean),
            upper=np.maximum(upper, mean),
            model_name=self.name,
            details={
                "aic": round(float(self.result.aic), 2),
                "residual_sigma": round(self.sigma, 4),
                "order": str(self.order),
                "seasonal_order": str(self.seasonal_order),
            },
        )


def fit_predict(
    dates_train,
    y_train,
    dates_pred,
    holidays: list[dict],
    *,
    model_name: str = "sarimax",
    promo_train=None,
    promo_pred=None,
) -> Prediction:
    """Обучает выбранную модель; при ошибке SARIMAX переходит на регрессию."""

    if model_name in {"sarimax", "auto"}:
        try:
            model = SarimaxModel().fit(dates_train, y_train, holidays, promo=promo_train)
            return model.predict(dates_pred, holidays, promo=promo_pred)
        except Exception as exc:  # noqa: BLE001 - нужен гарантированный fallback
            regression = SeasonalRegressionModel().fit(
                dates_train, y_train, holidays, promo=promo_train
            )
            prediction = regression.predict(dates_pred, holidays, promo=promo_pred)
            prediction.fallback = True
            prediction.details["sarimax_error"] = f"{type(exc).__name__}: {exc}"
            return prediction

    model = SeasonalRegressionModel().fit(dates_train, y_train, holidays, promo=promo_train)
    return model.predict(dates_pred, holidays, promo=promo_pred)
