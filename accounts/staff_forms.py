from future import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


class StaffUserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Повтор пароля", widget=forms.PasswordInput)
    role = forms.ModelChoiceField(
        label="Роль",
        queryset=Group.objects.all().order_by("name"),
        required=False,
        empty_label="— без роли —",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active")

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Пароли не совпадают")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            user.groups.clear()
            role = self.cleaned_data.get("role")
            if role:
                user.groups.add(role)
        return user


class StaffUserUpdateForm(forms.ModelForm):
    password1 = forms.CharField(label="Новый пароль (необязательно)", widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label="Повтор нового пароля", widget=forms.PasswordInput, required=False)
    role = forms.ModelChoiceField(
        label="Роль",
        queryset=Group.objects.all().order_by("name"),
        required=False,
        empty_label="— без роли —",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["role"].initial = self.instance.groups.first()

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if (p1 or p2) and p1 != p2:
            raise forms.ValidationError("Пароли не совпадают")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        p1 = self.cleaned_data.get("password1")
        if p1:
            user.set_password(p1)
        if commit:
            user.save()
            user.groups.clear()
            role = self.cleaned_data.get("role")
            if role:
                user.groups.add(role)
        return user