from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Пользователь системы (клиент, менеджер, администратор)"""
    ROLE_CHOICES = [
        ('client', 'Клиент'),
        ('manager', 'Менеджер'),
        ('admin', 'Администратор'),
    ]
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES, default='client')
    phone = models.CharField('Телефон', max_length=20, blank=True)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


class Customer(models.Model):
    """Клиент (физическое или юридическое лицо)"""
    TYPE_CHOICES = [
        ('physical', 'Физическое лицо'),
        ('legal', 'Юридическое лицо'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    customer_type = models.CharField('Тип клиента', max_length=20, choices=TYPE_CHOICES, default='physical')
    full_name = models.CharField('ФИО', max_length=200, blank=True)
    company_name = models.CharField('Название компании', max_length=200, blank=True)
    inn = models.CharField('ИНН', max_length=12, blank=True)
    address = models.TextField('Адрес доставки', blank=True)

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'


class Category(models.Model):
    """Категория товаров"""
    name = models.CharField('Название', max_length=100)
    description = models.TextField('Описание', blank=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'


class Product(models.Model):
    """Товар (цветы, букеты, композиции)"""
    name = models.CharField('Название', max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name='Категория')
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField('Остаток', default=0)
    description = models.TextField('Описание', blank=True)
    image = models.CharField('Изображение', max_length=255, blank=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'


class Supplier(models.Model):
    """Поставщик"""
    name = models.CharField('Название', max_length=200)
    contact_person = models.CharField('Контактное лицо', max_length=200, blank=True)
    phone = models.CharField('Телефон', max_length=20, blank=True)
    email = models.EmailField('Почта', blank=True)

    class Meta:
        verbose_name = 'Поставщик'
        verbose_name_plural = 'Поставщики'


class PeakDate(models.Model):
    """Пиковая дата (праздник: 8 марта, 14 февраля и т.д.)"""
    name = models.CharField('Название', max_length=100)
    month = models.IntegerField('Месяц')
    day = models.IntegerField('День')
    demand_coefficient = models.DecimalField('Коэффициент спроса', max_digits=4, decimal_places=2, default=1.0)
    description = models.TextField('Описание', blank=True)

    class Meta:
        verbose_name = 'Пиковая дата'
        verbose_name_plural = 'Пиковые даты'


class Order(models.Model):
    """Заказ"""
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('processing', 'В обработке'),
        ('ready', 'Готов'),
        ('completed', 'Выполнен'),
        ('cancelled', 'Отменён'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name='Клиент')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Менеджер')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')
    total_amount = models.DecimalField('Итоговая сумма', max_digits=10, decimal_places=2, default=0)
    delivery_date = models.DateField('Дата доставки', null=True, blank=True)
    delivery_address = models.TextField('Адрес доставки', blank=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'


class OrderItem(models.Model):
    """Позиция заказа"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Заказ')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='Товар')
    quantity = models.IntegerField('Количество')
    price_at_moment = models.DecimalField('Цена на момент', max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'


class Supply(models.Model):
    """Поставка от поставщика"""
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='Поставщик')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='Товар')
    quantity = models.IntegerField('Количество')
    purchase_price = models.DecimalField('Закупочная цена', max_digits=10, decimal_places=2)
    supply_date = models.DateField('Дата поставки')

    class Meta:
        verbose_name = 'Поставка'
        verbose_name_plural = 'Поставки'


class SalesHistory(models.Model):
    """История продаж (данные для прогноза)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Товар')
    sale_date = models.DateField('Дата продажи')
    quantity = models.IntegerField('Количество')
    revenue = models.DecimalField('Выручка', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'История продаж'
        verbose_name_plural = 'История продаж'
        unique_together = [['product', 'sale_date']]


class Forecast(models.Model):
    """Прогноз спроса (результат работы модели)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Товар')
    forecast_date = models.DateField('Дата прогноза')
    predicted_quantity = models.IntegerField('Предсказанное количество')
    lower_bound = models.IntegerField('Нижняя граница', null=True, blank=True)
    upper_bound = models.IntegerField('Верхняя граница', null=True, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Прогноз'
        verbose_name_plural = 'Прогнозы'