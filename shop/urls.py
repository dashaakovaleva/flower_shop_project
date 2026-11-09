from django.contrib.auth import views as auth_views
from django.urls import path

from shop import views
from shop.forms import StyledAuthenticationForm

urlpatterns = [
    path("", views.home, name="home"),
    path("docs/", views.docs_view, name="docs"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=StyledAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),
    path("register/", views.register, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<int:pk>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:pk>/", views.cart_add, name="cart_add"),
    path("cart/update/<int:pk>/", views.cart_update, name="cart_update"),
    path("cart/remove/<int:pk>/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("my-orders/", views.my_orders, name="my_orders"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/cancel/", views.order_cancel, name="order_cancel"),
    path("manager/orders/", views.manager_orders, name="manager_orders"),
    path("manager/orders/<int:pk>/status/", views.order_status_update, name="order_status_update"),
    path("manager/products/", views.manager_products, name="manager_products"),
    path("manager/products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("manager/supplies/", views.manager_supplies, name="manager_supplies"),
    path("forecast/", views.forecast_view, name="forecast"),
    path("forecast/run/", views.forecast_run, name="forecast_run"),
    path("analytics/", views.analytics_view, name="analytics"),
    path("analytics/run/", views.backtest_run_view, name="backtest_run"),
    path("analytics/comparison/", views.comparison_view, name="comparison"),
]
