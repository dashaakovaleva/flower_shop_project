"""Формы интерфейса: регистрация, оформление заказа, управление товарами."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Customer, Order, Product, SalesRecord, Supply, User


class StyledAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Введите логин", "autofocus": True}
        ),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Введите пароль"}
        ),
    )


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        label="Имя", max_length=150, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = forms.CharField(
        label="Фамилия",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="E-mail", widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+7 ..."}),
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone")
        widgets = {"username": forms.TextInput(attrs={"class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.update({"class": "form-control"})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data.get("last_name", "")
        user.phone = self.cleaned_data.get("phone", "")
        user.role = User.Role.CLIENT
        if commit:
            user.save()
            Customer.objects.create(
                user=user,
                full_name=user.get_full_name() or user.username,
                phone=user.phone,
                email=user.email,
                customer_type=Customer.CustomerType.PHYSICAL,
            )
        return user


class CheckoutForm(forms.Form):
    delivery_address = forms.CharField(
        label="Адрес доставки",
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Улица, дом, квартира"}
        ),
    )
    delivery_date = forms.DateField(
        label="Дата доставки",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    comment = forms.CharField(
        label="Комментарий к заказу",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    customer_type = forms.ChoiceField(
        label="Тип клиента",
        choices=Customer.CustomerType.choices,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    company_name = forms.CharField(
        label="Название компании (для юрлица)",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    inn = forms.CharField(
        label="ИНН (для юрлица)",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )


class OrderStatusForm(forms.Form):
    status = forms.ChoiceField(
        label="Новый статус",
        choices=Order.Status.choices,
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
    )


class ProductEditForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("price", "cost_price", "stock_quantity", "min_stock", "is_active")
        widgets = {
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cost_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "stock_quantity": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "min_stock": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class SupplyForm(forms.ModelForm):
    class Meta:
        model = Supply
        fields = ("supplier", "product", "quantity", "purchase_price", "supply_date", "comment")
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-control"}),
            "product": forms.Select(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "purchase_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "supply_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class SalesFilterForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    dataset = forms.ChoiceField(
        choices=[("", "Все наборы")] + list(SalesRecord.Dataset.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    date_from = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    date_to = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
