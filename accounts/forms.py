from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

from .permissions import ROLE_NAMES

User = get_user_model()


class StaffUserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(label="Повтор пароля", widget=forms.PasswordInput, required=True)

    role = forms.ModelChoiceField(
        label="Роль",
        queryset=Group.objects.filter(name__in=ROLE_NAMES).order_by("name"),
        required=True
    )

    class Meta:
        model = User
        # подстрой под твой User-модель при необходимости
        fields = ("username", "first_name", "last_name", "email")

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Пароли не совпадают")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            # одна роль = одна группа из ROLE_NAMES
            role = self.cleaned_data["role"]
            user.groups.set([role])
        return user


class StaffUserUpdateForm(forms.ModelForm):
    password1 = forms.CharField(label="Новый пароль", widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label="Повтор нового пароля", widget=forms.PasswordInput, required=False)

    role = forms.ModelChoiceField(
        label="Роль",
        queryset=Group.objects.filter(name__in=ROLE_NAMES).order_by("name"),
        required=True
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # проставим текущую роль (первую из ROLE_NAMES)
        current = self.instance.groups.filter(name__in=ROLE_NAMES).first()
        if current:
            self.initial["role"] = current

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if (p1 or p2) and p1 != p2:
            self.add_error("password2", "Пароли не совпадают")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)

        p1 = self.cleaned_data.get("password1")
        if p1:
            user.set_password(p1)

        if commit:
            user.save()
            role = self.cleaned_data["role"]
            user.groups.set([role])

        return user


class RoleForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        label="Права",
        queryset=Permission.objects.all().select_related("content_type").order_by("content_type__app_label", "codename"),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Group
        fields = ("name", "permissions")

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("Название роли обязательно")
        return name
