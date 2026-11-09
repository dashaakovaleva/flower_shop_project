from .analytics import analytics_view, backtest_run_view, comparison_view
from .auth import register
from .catalog import (
    cart_add,
    cart_remove,
    cart_update,
    cart_view,
    catalog,
    checkout,
    my_orders,
    order_cancel,
    order_detail,
    product_detail,
)
from .dashboard import dashboard
from .forecast import forecast_run, forecast_view
from .home import docs_view, home
from .manager import (
    manager_orders,
    manager_products,
    manager_supplies,
    order_status_update,
    product_edit,
)

__all__ = [
    "home",
    "docs_view",
    "register",
    "dashboard",
    "catalog",
    "product_detail",
    "cart_add",
    "cart_update",
    "cart_remove",
    "cart_view",
    "checkout",
    "my_orders",
    "order_detail",
    "order_cancel",
    "manager_orders",
    "order_status_update",
    "manager_products",
    "product_edit",
    "manager_supplies",
    "forecast_view",
    "forecast_run",
    "analytics_view",
    "backtest_run_view",
    "comparison_view",
]
