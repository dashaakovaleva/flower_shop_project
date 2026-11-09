# ER-диаграмма FloraIS

```mermaid
erDiagram
    USER ||--o| CUSTOMER : "профиль клиента"
    USER ||--o{ ORDER : "менеджер обрабатывает"
    CUSTOMER ||--o{ ORDER : "оформляет"
    ORDER ||--|{ ORDER_ITEM : "содержит"
    PRODUCT ||--o{ ORDER_ITEM : "входит в"
    CATEGORY ||--o{ PRODUCT : "классифицирует"
    SUPPLIER ||--o{ SUPPLY : "поставляет"
    PRODUCT ||--o{ SUPPLY : "принимается"
    PRODUCT ||--o{ SALES_RECORD : "имеет продажи"
    MODEL_RUN ||--o{ MODEL_METRIC : "содержит метрики"
    MODEL_RUN ||--o{ FORECAST : "строит прогноз"
    MODEL_RUN ||--o{ RECOMMENDATION : "формирует рекомендации"
    PRODUCT ||--o{ FORECAST : "прогнозируется"
    PRODUCT ||--o{ RECOMMENDATION : "рекомендуется"

    USER {
        int id PK
        string username
        string role "client|manager|admin"
        string phone
        string email
    }
    CUSTOMER {
        int id PK
        int user_id FK
        string customer_type "physical|legal"
        string full_name
        string company_name
        string inn
        string phone
        string address
    }
    CATEGORY {
        int id PK
        string name
        string slug
        string icon
        string accent
    }
    PRODUCT {
        int id PK
        int category_id FK
        string name
        string sku
        decimal price
        decimal cost_price
        int stock_quantity
        int min_stock
        bool is_active
    }
    SUPPLIER {
        int id PK
        string name
        string contact_person
        string phone
        string email
    }
    PEAK_DATE {
        int id PK
        string name
        int month
        int day
        decimal demand_coefficient
        int window_days
    }
    ORDER {
        int id PK
        int customer_id FK
        int manager_id FK
        string status
        string source
        date delivery_date
        text delivery_address
        decimal total_amount
        bool stock_deducted
        datetime created_at
    }
    ORDER_ITEM {
        int id PK
        int order_id FK
        int product_id FK
        int quantity
        decimal price_at_moment
    }
    SUPPLY {
        int id PK
        int supplier_id FK
        int product_id FK
        int quantity
        decimal purchase_price
        date supply_date
    }
    SALES_RECORD {
        int id PK
        int product_id FK
        date date
        int quantity
        decimal revenue
        string dataset "train|holdout"
        bool is_peak
        string holiday_name
        bool promo
    }
    REAL_MARKET_RECORD {
        int id PK
        date date
        float cut_flowers
        float pot_own
        float pot_purchased
        float wholesale
        float mean_temp
        float mean_humidity
        string public_holiday
    }
    MODEL_RUN {
        int id PK
        string kind "backtest|operational"
        string model_name
        string status
        date train_start
        date train_end
        date test_start
        date test_end
        int horizon_days
        json summary
    }
    MODEL_METRIC {
        int id PK
        int run_id FK
        string segment "all|normal|peak"
        int n_obs
        float mae
        float rmse
        float mape
        float wape
        float bias_pct
        float coverage_pct
    }
    FORECAST {
        int id PK
        int run_id FK
        int product_id FK
        date date
        float predicted_quantity
        float lower_bound
        float upper_bound
        float actual_quantity
        bool is_peak
    }
    RECOMMENDATION {
        int id PK
        int run_id FK
        int product_id FK
        int horizon_days
        float forecast_demand
        int current_stock
        float safety_stock
        float required_stock
        int purchase_quantity
        string priority
    }
```

## Связи и ограничения

| Связь | Кардинальность | Правило |
|-------|----------------|---------|
| User → Customer | 1 : 0..1 | клиентский профиль создаётся при регистрации |
| Customer → Order | 1 : N | заказ принадлежит одному клиенту |
| Order → OrderItem | 1 : N | позиции удаляются вместе с заказом (CASCADE) |
| Product → OrderItem | 1 : N | товар защищён от удаления (PROTECT) |
| Category → Product | 1 : N | категория защищена от удаления (PROTECT) |
| Product → Supply | 1 : N | поставка увеличивает остаток |
| Product → SalesRecord | 1 : N | уникальность `(product, date, dataset)` |
| ModelRun → Forecast | 1 : N | уникальность `(run, product, date)` |
| ModelRun → Recommendation | 1 : N | уникальность `(run, product)` |
| ModelRun → ModelMetric | 1 : N | уникальность `(run, segment)` |

## Индексы

- `Order(status, -created_at)`, `Order(created_at)`;
- `Product(is_active, category)`;
- `SalesRecord(date)`, `(dataset, date)`, `(product, dataset, date)`;
- `Forecast(run, date)`;
- `Supply(supply_date)`;
- `ModelRun(kind, -created_at)`.
