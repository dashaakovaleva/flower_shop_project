"""Модели предметной области информационной системы цветочного магазина."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Пользователь системы с одной из трёх ролей."""

    class Role(models.TextChoices):
        CLIENT = "client", "Клиент"
        MANAGER = "manager", "Менеджер"
        ADMIN = "admin", "Администратор"

    role = models.CharField(
        "Роль", max_length=20, choices=Role.choices, default=Role.CLIENT
    )
    phone = models.CharField("Телефон", max_length=30, blank=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def is_manager(self) -> bool:
        return self.is_superuser or self.role in {self.Role.MANAGER, self.Role.ADMIN}

    @property
    def is_admin_role(self) -> bool:
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def role_label(self) -> str:
        return self.get_role_display()

    @property
    def initials(self) -> str:
        full = self.get_full_name().strip()
        if full:
            parts = full.split()
            return "".join(part[0].upper() for part in parts[:2])
        return self.username[:2].upper()


class Customer(models.Model):
    """Клиент — физическое или юридическое лицо."""

    class CustomerType(models.TextChoices):
        PHYSICAL = "physical", "Физическое лицо"
        LEGAL = "legal", "Юридическое лицо"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_profile",
        verbose_name="Учётная запись",
    )
    customer_type = models.CharField(
        "Тип клиента",
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.PHYSICAL,
    )
    full_name = models.CharField("ФИО", max_length=200, blank=True)
    company_name = models.CharField("Название компании", max_length=200, blank=True)
    inn = models.CharField("ИНН", max_length=12, blank=True)
    phone = models.CharField("Телефон", max_length=30, blank=True)
    email = models.EmailField("E-mail", blank=True)
    address = models.TextField("Адрес доставки", blank=True)
    created_at = models.DateTimeField("Дата регистрации", auto_now_add=True)

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"
        ordering = ["full_name", "company_name"]

    def __str__(self) -> str:
        return self.full_name or self.company_name or f"Клиент №{self.pk}"

    @property
    def display_name(self) -> str:
        return self.full_name or self.company_name or f"Клиент №{self.pk}"


class Category(models.Model):
    """Категория товаров."""

    name = models.CharField("Название", max_length=100, unique=True)
    slug = models.SlugField("Слаг", max_length=100, unique=True, blank=True)
    description = models.TextField("Описание", blank=True)
    icon = models.CharField("Иконка", max_length=10, default="💐")
    accent = models.CharField("Цвет акцента", max_length=20, default="#1f7a5c")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """Товар магазина: цветы, букеты, композиции, декор."""

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Категория",
    )
    name = models.CharField("Название", max_length=200)
    sku = models.CharField("Артикул", max_length=40, unique=True)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField(
        "Цена продажи", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    cost_price = models.DecimalField(
        "Закупочная цена",
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    stock_quantity = models.PositiveIntegerField("Остаток на складе", default=0)
    min_stock = models.PositiveIntegerField("Минимальный остаток", default=5)
    unit = models.CharField("Единица измерения", max_length=20, default="шт.")
    image_emoji = models.CharField("Эмодзи", max_length=10, default="🌷")
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ["category__name", "name"]
        indexes = [models.Index(fields=["is_active", "category"])]

    def __str__(self) -> str:
        return self.name

    @property
    def margin(self) -> Decimal:
        if not self.price:
            return Decimal("0")
        return self.price - self.cost_price

    @property
    def margin_percent(self) -> float:
        if not self.price:
            return 0.0
        return float(self.margin / self.price * 100)

    @property
    def stock_status(self) -> str:
        if self.stock_quantity == 0:
            return "out"
        if self.stock_quantity <= self.min_stock:
            return "low"
        return "ok"

    @property
    def stock_status_label(self) -> str:
        return {"out": "Нет в наличии", "low": "Мало", "ok": "В наличии"}[
            self.stock_status
        ]


class Supplier(models.Model):
    """Поставщик товаров."""

    name = models.CharField("Название", max_length=200)
    contact_person = models.CharField("Контактное лицо", max_length=200, blank=True)
    phone = models.CharField("Телефон", max_length=30, blank=True)
    email = models.EmailField("Почта", blank=True)
    address = models.TextField("Адрес", blank=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Поставщик"
        verbose_name_plural = "Поставщики"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PeakDate(models.Model):
    """Праздничная (пиковая) дата, влияющая на спрос."""

    name = models.CharField("Название", max_length=100)
    month = models.PositiveSmallIntegerField(
        "Месяц", validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    day = models.PositiveSmallIntegerField(
        "День", validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    demand_coefficient = models.DecimalField(
        "Коэффициент спроса",
        max_digits=5,
        decimal_places=2,
        default=2.0,
        validators=[MinValueValidator(1)],
    )
    window_days = models.PositiveSmallIntegerField("Окно разгона, дней", default=10)
    color = models.CharField("Цвет", max_length=20, default="#e11d48")
    description = models.TextField("Описание", blank=True)

    class Meta:
        verbose_name = "Пиковая дата"
        verbose_name_plural = "Пиковые даты"
        ordering = ["month", "day"]
        unique_together = [["month", "day"]]

    def __str__(self) -> str:
        return self.name

    def date_in_year(self, year: int) -> date:
        return date(year, self.month, self.day)

    def next_occurrence(self, today: date | None = None) -> date:
        today = today or timezone.localdate()
        occurrence = self.date_in_year(today.year)
        if occurrence < today:
            occurrence = self.date_in_year(today.year + 1)
        return occurrence

    def days_until(self, today: date | None = None) -> int:
        return (self.next_occurrence(today) - (today or timezone.localdate())).days


class Order(models.Model):
    """Заказ клиента."""

    class Status(models.TextChoices):
        NEW = "new", "Новый"
        PROCESSING = "processing", "В обработке"
        READY = "ready", "Готов к выдаче"
        COMPLETED = "completed", "Выполнен"
        CANCELLED = "cancelled", "Отменён"

    class Source(models.TextChoices):
        ONLINE = "online", "Онлайн-магазин"
        OFFLINE = "offline", "Офис / телефон"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Клиент",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_orders",
        verbose_name="Менеджер",
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.NEW
    )
    source = models.CharField(
        "Источник", max_length=20, choices=Source.choices, default=Source.ONLINE
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)
    delivery_date = models.DateField("Дата доставки", null=True, blank=True)
    delivery_address = models.TextField("Адрес доставки", blank=True)
    comment = models.TextField("Комментарий", blank=True)
    total_amount = models.DecimalField(
        "Итоговая сумма", max_digits=12, decimal_places=2, default=0
    )
    stock_deducted = models.BooleanField("Остатки списаны", default=False)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Заказ {self.number}"

    @property
    def number(self) -> str:
        return f"FL-{self.pk:05d}" if self.pk else "FL-новая"

    @property
    def status_label(self) -> str:
        return self.get_status_display()

    @property
    def status_css(self) -> str:
        return {
            self.Status.NEW: "info",
            self.Status.PROCESSING: "warning",
            self.Status.READY: "success",
            self.Status.COMPLETED: "success",
            self.Status.CANCELLED: "danger",
        }.get(self.status, "info")

    @property
    def can_cancel(self) -> bool:
        return self.status not in {self.Status.COMPLETED, self.Status.CANCELLED}

    @property
    def status_choices(self):
        return self.Status.choices

    def recalculate_total(self) -> Decimal:
        total = sum((item.line_total for item in self.items.all()), Decimal("0"))
        self.total_amount = total
        self.save(update_fields=["total_amount", "updated_at"])
        return total


class OrderItem(models.Model):
    """Позиция заказа."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="order_items", verbose_name="Товар"
    )
    quantity = models.PositiveIntegerField("Количество", validators=[MinValueValidator(1)])
    price_at_moment = models.DecimalField(
        "Цена на момент заказа", max_digits=10, decimal_places=2
    )

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self) -> str:
        return f"{self.product.name} × {self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return self.price_at_moment * self.quantity


class Supply(models.Model):
    """Поставка товара от поставщика."""

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="supplies",
        verbose_name="Поставщик",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="supplies",
        verbose_name="Товар",
    )
    quantity = models.PositiveIntegerField("Количество", validators=[MinValueValidator(1)])
    purchase_price = models.DecimalField(
        "Закупочная цена", max_digits=10, decimal_places=2
    )
    supply_date = models.DateField("Дата поставки", default=timezone.localdate)
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Поставка"
        verbose_name_plural = "Поставки"
        ordering = ["-supply_date", "-created_at"]
        indexes = [models.Index(fields=["supply_date"])]

    def __str__(self) -> str:
        return f"{self.product.name} — {self.quantity} шт."


class SalesRecord(models.Model):
    """Агрегированная дневная продажа товара — основа прогнозной модели."""

    class Dataset(models.TextChoices):
        TRAIN = "train", "Синтетика (2 года обучения)"
        HOLDOUT = "holdout", "Отложенный год (имитация реальных продаж)"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="sales_records",
        verbose_name="Товар",
    )
    date = models.DateField("Дата")
    quantity = models.PositiveIntegerField("Количество", default=0)
    revenue = models.DecimalField("Выручка", max_digits=12, decimal_places=2, default=0)
    dataset = models.CharField(
        "Набор данных", max_length=20, choices=Dataset.choices, default=Dataset.TRAIN
    )
    is_peak = models.BooleanField("Пиковый день", default=False)
    holiday_name = models.CharField("Праздник", max_length=100, blank=True)
    promo = models.BooleanField("Акция", default=False)

    class Meta:
        verbose_name = "История продаж"
        verbose_name_plural = "История продаж"
        ordering = ["-date", "product"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "date", "dataset"], name="unique_product_date_dataset"
            )
        ]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["dataset", "date"]),
            models.Index(fields=["product", "dataset", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} — {self.date}: {self.quantity}"

    @property
    def unit_price(self) -> Decimal:
        if not self.quantity:
            return Decimal("0")
        return (self.revenue / self.quantity).quantize(Decimal("0.01"))


class RealMarketRecord(models.Model):
    """Внешний реальный датасет продаж цветочного магазина (референс)."""

    date = models.DateField("Дата", unique=True)
    cut_flowers = models.FloatField("Срезанные цветы", default=0)
    pot_own = models.FloatField("Горшечные растения собственные", default=0)
    pot_purchased = models.FloatField("Горшечные растения покупные", default=0)
    wholesale = models.FloatField("Опт", default=0)
    fruits_vegs = models.FloatField("Фрукты и овощи", default=0)
    commodity = models.FloatField("Сопутствующие товары", default=0)
    mean_temp = models.FloatField("Средняя температура", null=True, blank=True)
    mean_humidity = models.FloatField("Средняя влажность", null=True, blank=True)
    public_holiday = models.CharField("Государственный праздник", max_length=100, blank=True)
    school_holiday = models.CharField("Школьные каникулы", max_length=100, blank=True)
    source = models.CharField("Источник", max_length=200, default="CashierData.csv")

    class Meta:
        verbose_name = "Реальные продажи (внешний датасет)"
        verbose_name_plural = "Реальные продажи (внешний датасет)"
        ordering = ["date"]
        indexes = [models.Index(fields=["date"])]

    def __str__(self) -> str:
        return f"{self.date}: срезанные цветы — {self.cut_flowers:.0f}"


class ModelRun(models.Model):
    """Запуск обучения/прогноза: бэктест на отложенном годе или рабочий прогноз."""

    class Kind(models.TextChoices):
        BACKTEST = "backtest", "Бэктест (2 года → 3-й год)"
        OPERATIONAL = "operational", "Рабочий прогноз на 7 дней"

    class Status(models.TextChoices):
        RUNNING = "running", "Выполняется"
        COMPLETED = "completed", "Завершён"
        FAILED = "failed", "Ошибка"

    kind = models.CharField("Тип запуска", max_length=20, choices=Kind.choices)
    model_name = models.CharField("Модель", max_length=120)
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.RUNNING
    )
    train_start = models.DateField("Начало обучения", null=True, blank=True)
    train_end = models.DateField("Конец обучения", null=True, blank=True)
    test_start = models.DateField("Начало теста", null=True, blank=True)
    test_end = models.DateField("Конец теста", null=True, blank=True)
    horizon_days = models.PositiveSmallIntegerField("Горизонт, дней", default=7)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    params = models.JSONField("Параметры", default=dict, blank=True)
    summary = models.JSONField("Сводка", default=dict, blank=True)
    error_message = models.TextField("Ошибка", blank=True)

    class Meta:
        verbose_name = "Запуск модели"
        verbose_name_plural = "Запуски модели"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["kind", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — {self.created_at:%d.%m.%Y %H:%M}"

    @property
    def duration_seconds(self) -> float | None:
        return self.summary.get("duration_seconds") if self.summary else None

    def metric(self, segment: str) -> "ModelMetric | None":
        return self.metrics.filter(segment=segment).first()

    @property
    def metric_all(self) -> "ModelMetric | None":
        return self.metric(ModelMetric.Segment.ALL)

    @property
    def metric_normal(self) -> "ModelMetric | None":
        return self.metric(ModelMetric.Segment.NORMAL)

    @property
    def metric_peak(self) -> "ModelMetric | None":
        return self.metric(ModelMetric.Segment.PEAK)


class ModelMetric(models.Model):
    """Метрики качества модели по сегментам (все дни, обычные, пиковые)."""

    class Segment(models.TextChoices):
        ALL = "all", "Все дни"
        NORMAL = "normal", "Обычные дни"
        PEAK = "peak", "Пиковые дни"

    run = models.ForeignKey(
        ModelRun, on_delete=models.CASCADE, related_name="metrics", verbose_name="Запуск"
    )
    segment = models.CharField("Сегмент", max_length=20, choices=Segment.choices)
    n_obs = models.PositiveIntegerField("Наблюдений", default=0)
    mae = models.FloatField("MAE", default=0)
    rmse = models.FloatField("RMSE", default=0)
    mape = models.FloatField("MAPE, %", default=0)
    wape = models.FloatField("WAPE, %", default=0)
    bias_pct = models.FloatField("Смещение, %", default=0)
    coverage_pct = models.FloatField("Покрытие интервала, %", default=0)
    actual_mean = models.FloatField("Средний факт", default=0)
    predicted_mean = models.FloatField("Средний прогноз", default=0)

    class Meta:
        verbose_name = "Метрика модели"
        verbose_name_plural = "Метрики модели"
        unique_together = [["run", "segment"]]
        ordering = ["segment"]

    def __str__(self) -> str:
        return f"{self.run_id}: {self.get_segment_display()}"


class Forecast(models.Model):
    """Точка прогноза спроса."""

    run = models.ForeignKey(
        ModelRun, on_delete=models.CASCADE, related_name="forecasts", verbose_name="Запуск"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="forecasts", verbose_name="Товар"
    )
    date = models.DateField("Дата")
    predicted_quantity = models.FloatField("Прогноз")
    lower_bound = models.FloatField("Нижняя граница", default=0)
    upper_bound = models.FloatField("Верхняя граница", default=0)
    actual_quantity = models.FloatField("Факт", null=True, blank=True)
    is_peak = models.BooleanField("Пиковый день", default=False)
    holiday_name = models.CharField("Праздник", max_length=100, blank=True)

    class Meta:
        verbose_name = "Прогноз"
        verbose_name_plural = "Прогнозы"
        ordering = ["date", "product"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "product", "date"], name="unique_run_product_date"
            )
        ]
        indexes = [models.Index(fields=["run", "date"])]

    def __str__(self) -> str:
        return f"{self.product.name} — {self.date}: {self.predicted_quantity:.1f}"

    @property
    def error(self) -> float | None:
        if self.actual_quantity is None:
            return None
        return self.predicted_quantity - self.actual_quantity

    @property
    def abs_error(self) -> float | None:
        error = self.error
        return abs(error) if error is not None else None


class Recommendation(models.Model):
    """Рекомендация по дозакупке товара."""

    class Priority(models.TextChoices):
        CRITICAL = "critical", "Критичный"
        HIGH = "high", "Высокий"
        MEDIUM = "medium", "Средний"
        LOW = "low", "Низкий"

    run = models.ForeignKey(
        ModelRun,
        on_delete=models.CASCADE,
        related_name="recommendations",
        verbose_name="Запуск",
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="recommendations", verbose_name="Товар"
    )
    horizon_days = models.PositiveSmallIntegerField("Горизонт, дней", default=7)
    forecast_demand = models.FloatField("Прогноз спроса")
    current_stock = models.PositiveIntegerField("Текущий остаток")
    safety_stock = models.FloatField("Страховой запас")
    required_stock = models.FloatField("Требуемый запас")
    purchase_quantity = models.PositiveIntegerField("Рекомендуемая закупка")
    priority = models.CharField("Приоритет", max_length=20, choices=Priority.choices)
    reason = models.TextField("Обоснование", blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Рекомендация по закупке"
        verbose_name_plural = "Рекомендации по закупке"
        ordering = ["-created_at", "priority"]
        unique_together = [["run", "product"]]

    def __str__(self) -> str:
        return f"{self.product.name}: закупить {self.purchase_quantity}"

    @property
    def priority_label(self) -> str:
        return self.get_priority_display()

    @property
    def priority_css(self) -> str:
        return {
            self.Priority.CRITICAL: "danger",
            self.Priority.HIGH: "warning",
            self.Priority.MEDIUM: "info",
            self.Priority.LOW: "success",
        }.get(self.priority, "info")

    @property
    def coverage_percent(self) -> float:
        if self.required_stock <= 0:
            return 100.0
        return min(100.0, self.current_stock / self.required_stock * 100)
