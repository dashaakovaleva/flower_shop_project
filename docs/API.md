# REST API FloraIS

Базовый URL: `http://127.0.0.1:8000/api/`

Интерактивный browsable-интерфейс: <http://127.0.0.1:8000/api/>

## Аутентификация

Поддерживаются:

- **Session Authentication** — вход через веб-форму, cookie `sessionid`;
- **Basic Authentication** — заголовок `Authorization: Basic base64(login:password)`.

```bash
curl -u manager:manager123 http://127.0.0.1:8000/api/products/
```

Права:

| Роль | Чтение каталога | Изменение каталога | Заказы | Аналитика |
|------|:---------------:|:------------------:|:------:|:---------:|
| Аноним | ✅ | ❌ | ❌ | ❌ |
| Клиент | ✅ | ❌ | только свои | ❌ |
| Менеджер | ✅ | ✅ | все | ✅ |
| Администратор | ✅ | ✅ | все | ✅ |

## Пагинация

По умолчанию 50 записей на страницу:

```json
{
  "count": 16,
  "next": null,
  "previous": null,
  "results": []
}
```

Параметр `?page=2`.

---

## Каталог

### `GET /api/categories/`

Список категорий с числом товаров.

### `GET /api/products/`

Параметры:

| Параметр | Описание |
|----------|----------|
| `search` | поиск по названию, SKU, описанию |
| `ordering` | `name`, `price`, `stock_quantity`, `created_at` |
| `category` | slug категории |
| `low=1` | только товары с остатком ≤ минимального |
| `page` | номер страницы |

```bash
curl "http://127.0.0.1:8000/api/products/?category=roses&ordering=price"
```

Пример ответа:

```json
{
  "id": 1,
  "category": 1,
  "category_name": "Розы",
  "name": "Роза красная 60 см",
  "sku": "ROSE-RED-60",
  "price": "220.00",
  "cost_price": "110.00",
  "stock_quantity": 160,
  "min_stock": 40,
  "stock_status": "ok",
  "margin_percent": 50.0
}
```

### `GET /api/suppliers/`

Только менеджер и администратор.

### `GET /api/peaks/`

Пиковые даты с `days_until` и `next_occurrence`.

---

## Заказы

### `GET /api/orders/`

Клиент получает только свои заказы, менеджер — все.

### `POST /api/orders/`

Клиент указывает только позиции; клиент и источник определяются автоматически.

```bash
curl -u client:client123 \
  -H "Content-Type: application/json" \
  -d '{
        "items": [{"product": 1, "quantity": 2}],
        "delivery_address": "Москва, ул. Цветочная, 7",
        "comment": "Доставить к 12:00"
      }' \
  http://127.0.0.1:8000/api/orders/
```

Менеджер обязан передать `customer`; `manager` подставляется автоматически.

Ответ `201 Created`:

```json
{
  "id": 31,
  "number": "FL-00031",
  "customer": 1,
  "customer_name": "Анна Смирнова",
  "status": "new",
  "status_label": "Новый",
  "total_amount": "440.00",
  "items": [
    {"product": 1, "product_name": "Роза красная 60 см", "quantity": 2}
  ]
}
```

Ошибки:

- `400` — недостаточно товара, пустой список позиций, отсутствует клиент;
- `403` — нет прав;
- `401` — не аутентифицирован.

### `POST /api/orders/{id}/set_status/`

Только менеджер/администратор.

```json
{"status": "processing"}
```

Допустимые статусы: `new`, `processing`, `ready`, `completed`, `cancelled`.

### `POST /api/orders/{id}/cancel/`

Отменяет заказ и возвращает остатки. Доступно владельцу или менеджеру.

---

## Аналитика и прогноз

### `GET /api/dashboard/summary/`

Только менеджер/администратор. Выручка и количество за 30 дней,
число заказов, товары с низким остатком, последние запуски модели.

### `GET /api/forecast/now/`

Последний рабочий прогноз и рекомендации. `404`, если прогноз ещё не строился.

### `POST /api/forecast/now/`

Запускает новый рабочий прогноз. Может занять несколько минут.

### `GET /api/analytics/metrics/`

Последний завершённый бэктест: модель, периоды, summary и метрики по сегментам.

```json
{
  "id": 6,
  "model_name": "SARIMAX(1,0,1)(1,0,1,7) + экзогенные признаки",
  "metrics": [
    {"segment": "all", "mae": 3.157, "rmse": 11.014, "mape": 22.676}
  ]
}
```

### `GET /api/analytics/comparison/`

Сравнение синтетики с внешним реальным датасетом:

```json
{
  "run_id": 6,
  "comparison": {
    "available": true,
    "weekly_correlation": 0.9963,
    "monthly_correlation": 0.0723,
    "ks_statistic": 0.2185,
    "ks_pvalue": 0.0
  }
}
```

### `GET /api/runs/`

История запусков модели. Фильтр `?kind=backtest` или `?kind=operational`.

### `GET /api/forecasts/?run=6&product=1`

Точки прогноза. Только менеджер/администратор.

### `GET /api/recommendations/?run=5&priority=critical`

Рекомендации по закупке.

### `GET /api/sales/`

История продаж. Фильтры: `product`, `dataset`, `date_from`, `date_to`.

### `GET /api/real-market/`

Внешний реальный датасет.

---

## Коды ответов

| Код | Значение |
|-----|----------|
| 200 | успех |
| 201 | создано |
| 204 | удалено |
| 400 | ошибка валидации |
| 401 | требуется аутентификация |
| 403 | недостаточно прав |
| 404 | объект не найден |
| 405 | метод не поддерживается |

## Ограничения

- `OrderViewSet` поддерживает только `GET` и `POST`;
- `SalesRecord`, `Forecast`, `ModelRun`, `Recommendation`, `RealMarketRecord` —
  только чтение;
- удаление товара или категории, на которые ссылаются заказы, запрещено
  (`PROTECT`).
