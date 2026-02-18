from __future__ import annotations

import re
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounts.models import Profile


User = get_user_model()

LATIN_RE = re.compile(r"^[A-Za-z][A-Za-z\s'\-]*$")


def validate_latin_optional(value: str, label: str):
    v = (value or "").strip()
    if not v:
        return ""
    if not LATIN_RE.match(v):
        raise ValidationError(f"{label} должно быть латиницей (A-Z), допускаются пробел/дефис/апостроф.")
    return v


class UserBasicsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "last_name", "first_name", "patronymic", "email", "phone"]

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Username обязателен.")
        qs = User.objects.filter(username=username).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Такой username уже занят.")
        return username

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip()


class EmployeeProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
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
        widgets = {"additional_skills": forms.Textarea(attrs={"rows": 4})}

    def clean_last_name_lat(self):
        v = (self.cleaned_data.get("last_name_lat") or "").strip()
        if v and not LATIN_RE.match(v):
            raise ValidationError("Фамилия латиницей должна быть латиницей (A-Z), допускаются пробел/дефис/апостроф.")
        return v

    def clean_first_name_lat(self):
        v = (self.cleaned_data.get("first_name_lat") or "").strip()
        if v and not LATIN_RE.match(v):
            raise ValidationError("Имя латиницей должно быть латиницей (A-Z), допускаются пробел/дефис/апостроф.")
        return v

    def clean_patronymic_lat(self):
        return validate_latin_optional(self.cleaned_data.get("patronymic_lat"), "Отчество латиницей")