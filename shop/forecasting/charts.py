"""Построение интерактивных графиков Plotly для HTML-интерфейса."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

EMERALD = "#1f7a5c"
DARK_GREEN = "#0f3d2e"
ROSE = "#e11d48"
GOLD = "#d4a373"
INK = "#26352b"
MUTED = "#6b7c72"
GRID = "#e6ece7"

PLOT_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
    "scrollZoom": False,
}


def _base_layout(title: str = "", height: int = 340) -> dict:
    return {
        "title": {
            "text": title,
            "font": {"size": 15, "color": INK, "family": "Segoe UI, sans-serif"},
            "x": 0.01,
        },
        "height": height,
        "margin": {"l": 42, "r": 18, "t": 48 if title else 18, "b": 38},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Segoe UI, sans-serif", "color": MUTED, "size": 12},
        "xaxis": {"gridcolor": GRID, "zeroline": False, "showline": False},
        "yaxis": {"gridcolor": GRID, "zeroline": False, "showline": False},
        "hovermode": "x unified",
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11},
        },
    }


def _html(figure: go.Figure, div_id: str) -> str:
    return pio.to_html(
        figure,
        include_plotlyjs=False,
        full_html=False,
        div_id=div_id,
        config=PLOT_CONFIG,
    )


def revenue_chart(frame: pd.DataFrame, title: str = "Выручка по дням") -> str:
    if frame.empty:
        return ""
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=frame["date"],
            y=frame["revenue"],
            mode="lines",
            name="Выручка",
            line={"color": EMERALD, "width": 2.4},
            fill="tozeroy",
            fillcolor="rgba(31,122,92,0.10)",
            hovertemplate="%{x|%d.%m.%Y}<br>%{y:,.0f} ₽<extra></extra>",
        )
    )
    figure.update_layout(**_base_layout(title))
    figure.update_yaxes(tickformat=",.0f", ticksuffix=" ₽")
    return _html(figure, "chart-revenue")


def forecast_chart(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    *,
    product_label: str = "Все товары",
) -> str:
    figure = go.Figure()
    if not history.empty:
        figure.add_trace(
            go.Scatter(
                x=history["date"],
                y=history["quantity"],
                mode="lines",
                name="История",
                line={"color": INK, "width": 1.9},
                hovertemplate="%{x|%d.%m.%Y}<br>факт: %{y:.0f}<extra></extra>",
            )
        )

    if not forecast.empty:
        figure.add_trace(
            go.Scatter(
                x=forecast["date"],
                y=forecast["upper"],
                mode="lines",
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=forecast["date"],
                y=forecast["lower"],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor="rgba(225,29,72,0.12)",
                name="80% интервал",
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=forecast["date"],
                y=forecast["predicted"],
                mode="lines+markers",
                name="Прогноз",
                line={"color": ROSE, "width": 2.6},
                marker={"size": 7, "color": ROSE},
                hovertemplate="%{x|%d.%m.%Y}<br>прогноз: %{y:.1f}<extra></extra>",
            )
        )
        peaks = forecast[forecast["is_peak"].astype(bool)]
        if not peaks.empty:
            figure.add_trace(
                go.Scatter(
                    x=peaks["date"],
                    y=peaks["predicted"],
                    mode="markers+text",
                    name="Пиковая дата",
                    marker={"size": 12, "color": GOLD, "symbol": "star"},
                    text=peaks["holiday_name"].fillna("").str[:18],
                    textposition="top center",
                    textfont={"size": 10, "color": GOLD},
                    hovertemplate="%{x|%d.%m.%Y}<br>%{text}<extra></extra>",
                )
            )

    figure.update_layout(**_base_layout(f"Прогноз спроса: {product_label}", height=390))
    figure.update_yaxes(title_text="Количество, шт.")
    return _html(figure, "chart-forecast")


def backtest_chart(frame: pd.DataFrame, title: str = "Факт и прогноз на отложенном году") -> str:
    if frame.empty:
        return ""
    daily = (
        frame.groupby("date", as_index=False)
        .agg(actual=("actual", "sum"), predicted=("predicted", "sum"))
        .sort_values("date")
    )
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=daily["date"],
            y=daily["actual"],
            mode="lines",
            name="Факт",
            line={"color": INK, "width": 1.8},
            hovertemplate="%{x|%d.%m.%Y}<br>факт: %{y:.0f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=daily["date"],
            y=daily["predicted"],
            mode="lines",
            name="Прогноз",
            line={"color": ROSE, "width": 2.0},
            hovertemplate="%{x|%d.%m.%Y}<br>прогноз: %{y:.0f}<extra></extra>",
        )
    )
    figure.update_layout(**_base_layout(title, height=390))
    figure.update_yaxes(title_text="Суммарные продажи, шт.")
    return _html(figure, "chart-backtest")


def weekly_comparison_chart(stats: dict) -> str:
    if not stats.get("available"):
        return ""
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    synthetic = [stats["weekly_synthetic"].get(str(i), stats["weekly_synthetic"].get(i, 0)) for i in range(7)]
    real = [stats["weekly_real"].get(str(i), stats["weekly_real"].get(i, 0)) for i in range(7)]
    figure = go.Figure(
        data=[
            go.Bar(name="Синтетика (2 года)", x=days, y=synthetic, marker_color=EMERALD),
            go.Bar(name="Реальный датасет", x=days, y=real, marker_color=GOLD),
        ]
    )
    figure.update_layout(**_base_layout("Недельный профиль спроса (нормированный)", height=340))
    figure.update_layout(barmode="group")
    figure.update_yaxes(title_text="Доля от среднего")
    return _html(figure, "chart-weekly-comparison")


def monthly_comparison_chart(stats: dict) -> str:
    if not stats.get("available"):
        return ""
    months = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
    synthetic = [
        stats["monthly_synthetic"].get(str(i), stats["monthly_synthetic"].get(i, 0))
        for i in range(1, 13)
    ]
    real = [
        stats["monthly_real"].get(str(i), stats["monthly_real"].get(i, 0))
        for i in range(1, 13)
    ]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=months,
            y=synthetic,
            mode="lines+markers",
            name="Синтетика",
            line={"color": EMERALD, "width": 2.4},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=months,
            y=real,
            mode="lines+markers",
            name="Реальный датасет",
            line={"color": GOLD, "width": 2.4},
        )
    )
    figure.update_layout(**_base_layout("Месячный профиль спроса (нормированный)", height=340))
    figure.update_yaxes(title_text="Доля от среднего")
    return _html(figure, "chart-monthly-comparison")


def metrics_comparison_chart(metrics: list[dict]) -> str:
    normal = next((m for m in metrics if m["segment"] == "normal"), None)
    peak = next((m for m in metrics if m["segment"] == "peak"), None)
    labels = ["MAE", "RMSE", "MAPE, %"]
    normal_values = [normal["mae"], normal["rmse"], normal["mape"]] if normal else [0, 0, 0]
    peak_values = [peak["mae"], peak["rmse"], peak["mape"]] if peak else [0, 0, 0]
    figure = go.Figure(
        data=[
            go.Bar(name="Обычные дни", x=labels, y=normal_values, marker_color=EMERALD),
            go.Bar(name="Пиковые дни", x=labels, y=peak_values, marker_color=ROSE),
        ]
    )
    figure.update_layout(**_base_layout("Ошибки на обычных и пиковых днях", height=320))
    figure.update_layout(barmode="group")
    return _html(figure, "chart-metrics")


def top_products_chart(frame: pd.DataFrame, title: str = "Топ товаров по выручке") -> str:
    if frame.empty:
        return ""
    data = frame.sort_values("revenue", ascending=True).tail(8)
    figure = go.Figure(
        go.Bar(
            x=data["revenue"],
            y=data["product__name"],
            orientation="h",
            marker_color=EMERALD,
            hovertemplate="%{y}<br>%{x:,.0f} ₽<extra></extra>",
        )
    )
    figure.update_layout(**_base_layout(title, height=340))
    figure.update_xaxes(tickformat=",.0f", ticksuffix=" ₽")
    return _html(figure, "chart-top-products")


def demand_error_histogram(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    errors = (frame["predicted"] - frame["actual"]).to_numpy()
    figure = go.Figure(
        go.Histogram(
            x=errors,
            nbinsx=40,
            marker_color=EMERALD,
            opacity=0.8,
            hovertemplate="Ошибка: %{x:.1f}<br>Частота: %{y}<extra></extra>",
        )
    )
    figure.add_vline(x=0, line_dash="dash", line_color=ROSE)
    figure.update_layout(**_base_layout("Распределение ошибки прогноза (прогноз − факт)", height=320))
    figure.update_xaxes(title_text="Ошибка, шт.")
    figure.update_yaxes(title_text="Количество наблюдений")
    return _html(figure, "chart-error-histogram")
