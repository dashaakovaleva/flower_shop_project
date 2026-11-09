from django.utils import timezone


def global_context(request):
    """Общие данные для всех шаблонов: роль, корзина, текущая дата."""

    user = getattr(request, "user", None)
    cart = request.session.get("cart", {}) if hasattr(request, "session") else {}
    return {
        "today": timezone.localdate(),
        "cart_count": sum(int(qty) for qty in cart.values()) if cart else 0,
        "current_user_is_manager": bool(
            user and user.is_authenticated and getattr(user, "is_manager", False)
        ),
        "current_user_is_admin": bool(
            user and user.is_authenticated and getattr(user, "is_admin_role", False)
        ),
    }
