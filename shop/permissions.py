"""Разграничение доступа по ролям для представлений и REST API."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from rest_framework.permissions import SAFE_METHODS, BasePermission


def user_has_role(user, *roles: str) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) in roles)
    )


def role_required(*roles: str):
    """Декоратор для Django-представлений: доступ только указанным ролям."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if user_has_role(request.user, *roles):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("Недостаточно прав для выполнения операции")

        return wrapper

    return decorator


class IsManagerOrAdmin(BasePermission):
    message = "Операция доступна только менеджеру или администратору."

    def has_permission(self, request, view):
        return user_has_role(request.user, "manager", "admin")


class IsAdminRole(BasePermission):
    message = "Операция доступна только администратору."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or getattr(request.user, "role", None) == "admin")
        )


class IsManagerOrAdminOrReadOnly(BasePermission):
    """Читать могут все, изменять — менеджер и администратор."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return user_has_role(request.user, "manager", "admin")


class IsOwnerOrManager(BasePermission):
    """Клиент видит только свои заказы, менеджер — все."""

    def has_object_permission(self, request, view, obj):
        if user_has_role(request.user, "manager", "admin"):
            return True
        customer = getattr(request.user, "customer_profile", None)
        return bool(customer and obj.customer_id == customer.id)
