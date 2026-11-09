from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


@register.filter
def ru_month(value):
    try:
        return MONTHS.get(int(value), "")
    except (TypeError, ValueError):
        return ""


@register.filter
def weekday_ru(value):
    try:
        return WEEKDAYS[int(value)]
    except (TypeError, ValueError, IndexError):
        return ""


@register.filter
def money(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    formatted = f"{number:,.0f}".replace(",", " ")
    return f"{formatted} ₽"


@register.filter
def number(value):
    try:
        return f"{float(value):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return value


@register.filter
def dict_get(value, key):
    if not isinstance(value, dict):
        return None
    return value.get(key, value.get(str(key)))


@register.filter
def percent(value):
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


@register.filter
def as_percent(value):
    """Превращает долю (0.15) в проценты (15%)."""
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "—"


@register.filter
def status_css(value):
    return {
        "new": "info",
        "processing": "warning",
        "ready": "success",
        "completed": "success",
        "cancelled": "danger",
        "critical": "danger",
        "high": "warning",
        "medium": "info",
        "low": "success",
    }.get(value, "neutral")
