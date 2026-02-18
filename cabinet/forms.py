from __future__ import annotations

import re
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounts.models import Profile

User = get_user_model()

LATIN_RE = re.compile(r"^[A-Za-z][A-Za-z\s'\-]*$")


def _latin_required(value: str, label: str):
    v = (value or "").strip()
    if not v:
        raise ValidationError(f"{label} обязательно.")
    if not LATIN_RE.match(v):
        raise ValidationError(f"{label} должно быть латиницей (A-Z), допускаются пробел/дефис/апостроф.")
    return v


def _latin_optional(value: str, label: str):
    v = (value or "").strip()
    if not v:
        return ""
    if not LATIN_RE.match(v):
        raise ValidationError(f"{label} должно быть латиницей (A-Z), допускаются пробел/дефис/апостроф.")
    return v


class ProfileForm(forms.ModelForm):
    """
    ✅ Совместимость: cabinet/views.py ожидает ProfileForm(instance=request.user)
    Это форма для "Редактировать профиль" в кабинете.
    Правит:
      - поля User: username, last_name, first_name, patronymic, email, phone
      - поля анкеты Profile (включая photo/resume)
    """

    # --- поля аккаунта (User) ---
    username = forms.CharField(label="Username *", max_length=150)
    last_name = forms.CharField(label="Фамилия *", max_length=150)
    first_name = forms.CharField(label="Имя *", max_length=150)
    patronymic = forms.CharField(label="Отчество (если есть)", max_length=150, required=False)
    email = forms.EmailField(label="Почта *", required=True)
    phone = forms.CharField(label="Телефон *", max_length=30, required=True)

    class Meta:
        model = Profile
        fields = [
            # анкета
            "last_name_lat",
            "first_name_lat",
            "patronymic_lat",
            "gender",
            "citizenship",
            "telegram",

            "qualification",
            "travel_ready",
            "quarantine_ready",

            "restrictions_companies",
            "restrictions_topics",
            "restrictions_schedule",

            "fso_status",
            "own_equipment",

            "education",
            "additional_skills",

            "resume",
            "photo",
        ]
        widgets = {
            "additional_skills": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        """
        instance здесь ожидается как User (так исторически было у тебя в проекте).
        Мы сохраняем этот контракт.
        """
        self.user_instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

        if self.user_instance is None:
            return

        # подтянуть/создать профиль пользователя
        self.profile_instance, _ = Profile.objects.get_or_create(user=self.user_instance)
        # подменяем instance для ModelForm(Profile)
        self.instance = self.profile_instance

        # заполнить user-поля начальными значениями
        self.fields["username"].initial = getattr(self.user_instance, "username", "")
        self.fields["last_name"].initial = getattr(self.user_instance, "last_name", "")
        self.fields["first_name"].initial = getattr(self.user_instance, "first_name", "")
        self.fields["patronymic"].initial = getattr(self.user_instance, "patronymic", "")
        self.fields["email"].initial = getattr(self.user_instance, "email", "")
        self.fields["phone"].initial = getattr(self.user_instance, "phone", "")

    # --- валидации User ---
    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Username обязателен.")
        qs = User.objects.filter(username=username)
        if self.user_instance is not None:
            qs = qs.exclude(pk=self.user_instance.pk)
        if qs.exists():
            raise ValidationError("Такой username уже занят.")
        return username

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip()

    # --- валидации латиницы анкеты ---
    def clean_last_name_lat(self):
        return _latin_required(self.cleaned_data.get("last_name_lat"), "Фамилия латиницей")

    def clean_first_name_lat(self):
        return _latin_required(self.cleaned_data.get("first_name_lat"), "Имя латиницей")

    def clean_patronymic_lat(self):
        return _latin_optional(self.cleaned_data.get("patronymic_lat"), "Отчество латиницей")

    def save(self, commit=True):
        """
        Сохраняем и User, и Profile.
        """
        if self.user_instance is None:
            raise ValueError("ProfileForm ожидает instance=User")

        # 1) сохранить User
        u = self.user_instance
        u.username = self.cleaned_data["username"].strip()
        u.last_name = self.cleaned_data["last_name"].strip()
        u.first_name = self.cleaned_data["first_name"].strip()
        if hasattr(u, "patronymic"):
            u.patronymic = (self.cleaned_data.get("patronymic") or "").strip()
        u.email = (self.cleaned_data.get("email") or "").strip()
        if hasattr(u, "phone"):
            u.phone = (self.cleaned_data.get("phone") or "").strip()

        if commit:
            u.save()

        # 2) сохранить Profile (анкета)
        profile = super().save(commit=False)
        profile.user = u

        if commit:
            profile.save()
            self.save_m2m()

        return profile