from __future__ import annotations

import re
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Profile


User = get_user_model()

LATIN_RE = re.compile(r"^[A-Za-z][A-Za-z\s'\-]*$")


def validate_latin(value: str, label: str):
    v = (value or "").strip()
    if not v:
        raise ValidationError(f"{label} обязательно.")
    if not LATIN_RE.match(v):
        raise ValidationError(f"{label} должно быть латиницей (A-Z), допускаются пробел/дефис/апостроф.")
    return v


def validate_latin_optional(value: str, label: str):
    v = (value or "").strip()
    if not v:
        return ""
    if not LATIN_RE.match(v):
        raise ValidationError(f"{label} должно быть латиницей (A-Z), допускаются пробел/дефис/апостроф.")
    return v


class EmployeeRegistrationForm(forms.Form):
    username = forms.CharField(label="Username *", max_length=150)
    email = forms.EmailField(label="Почта *")
    password1 = forms.CharField(label="Пароль *", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Повтор пароля *", widget=forms.PasswordInput)

    last_name = forms.CharField(label="Фамилия *", max_length=150)
    first_name = forms.CharField(label="Имя *", max_length=150)
    patronymic = forms.CharField(label="Отчество (если есть)", max_length=150, required=False)

    last_name_lat = forms.CharField(label="Фамилия латиницей *", max_length=150)
    first_name_lat = forms.CharField(label="Имя латиницей *", max_length=150)
    patronymic_lat = forms.CharField(label="Отчество латиницей (если есть)", max_length=150, required=False)

    phone = forms.CharField(label="Номер телефона *", max_length=30)

    gender = forms.ChoiceField(label="Пол *", choices=[("", "— выберите —")] + list(Profile.Gender.choices))
    citizenship = forms.ChoiceField(
        label="Гражданство *",
        choices=list(Profile.Citizenship.choices),
        initial=Profile.Citizenship.RU,
    )
    telegram = forms.CharField(label="Телеграм *", max_length=150, help_text="Если отсутствует — напишите")

    qualification = forms.CharField(label="Квалификация, навыки *", max_length=255)
    travel_ready = forms.ChoiceField(
        label="Готовность к командировкам *",
        choices=[("", "— выберите —")] + list(Profile.YesNoMaybe.choices),
    )
    quarantine_ready = forms.ChoiceField(
        label="Готовность к карантину *",
        choices=[("", "— выберите —")] + list(Profile.YesNoMaybe.choices),
    )

    restrictions_companies = forms.CharField(label="Ограничения по работе с компаниями *", max_length=255, initial="Нет")
    restrictions_topics = forms.CharField(
        label="Ограничение на участие в проектах с определенной тематикой *",
        max_length=255,
        initial="Нет",
    )
    restrictions_schedule = forms.CharField(
        label="Ограничения по графику работы *",
        max_length=255,
        initial="Нет",
        help_text="Например: Семья дома ждёт после 18:00",
    )

    fso_status = forms.ChoiceField(
        label="Прохождение ФСО *",
        choices=[("", "— выберите —")] + list(Profile.FSOStatus.choices),
    )

    own_equipment = forms.CharField(
        label="Наличие собственного оборудования",
        max_length=255,
        required=False,
        initial="Нет",
        help_text="Световое оборудование, оборудование для съемки и проведения трансляций",
    )

    education = forms.ChoiceField(
        label="Образование *",
        choices=[("", "— выберите —")] + list(Profile.Education.choices),
    )

    additional_skills = forms.CharField(
        label="Дополнительные навыки",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    resume = forms.FileField(label="Резюме *", required=True)
    photo = forms.ImageField(
        label="Фото *",
        required=True,
        help_text="Фото как на паспорт: без очков, головных уборов, белый фон",
    )

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Username обязателен.")
        if User.objects.filter(username=username).exists():
            raise ValidationError("Такой username уже существует.")
        return username

    # ✅ латиница
    def clean_last_name_lat(self):
        return validate_latin(self.cleaned_data.get("last_name_lat"), "Фамилия латиницей")

    def clean_first_name_lat(self):
        return validate_latin(self.cleaned_data.get("first_name_lat"), "Имя латиницей")

    def clean_patronymic_lat(self):
        return validate_latin_optional(self.cleaned_data.get("patronymic_lat"), "Отчество латиницей")

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Пароли не совпадают.")
        return cleaned

    def save(self) -> User:
        user = User.objects.create_user(
            username=self.cleaned_data["username"].strip(),
            password=self.cleaned_data["password1"],
            email=(self.cleaned_data.get("email") or "").strip(),
            first_name=(self.cleaned_data.get("first_name") or "").strip(),
            last_name=(self.cleaned_data.get("last_name") or "").strip(),
        )

        if hasattr(user, "patronymic"):
            user.patronymic = (self.cleaned_data.get("patronymic") or "").strip()

        if hasattr(user, "phone"):
            user.phone = (self.cleaned_data.get("phone") or "").strip()

        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)

        profile.last_name_lat = (self.cleaned_data.get("last_name_lat") or "").strip()
        profile.first_name_lat = (self.cleaned_data.get("first_name_lat") or "").strip()
        profile.patronymic_lat = (self.cleaned_data.get("patronymic_lat") or "").strip()

        profile.gender = self.cleaned_data.get("gender") or ""
        profile.citizenship = self.cleaned_data.get("citizenship") or Profile.Citizenship.RU
        profile.telegram = (self.cleaned_data.get("telegram") or "").strip()

        profile.qualification = (self.cleaned_data.get("qualification") or "").strip()
        profile.travel_ready = self.cleaned_data.get("travel_ready") or ""
        profile.quarantine_ready = self.cleaned_data.get("quarantine_ready") or ""

        profile.restrictions_companies = (self.cleaned_data.get("restrictions_companies") or "Нет").strip()
        profile.restrictions_topics = (self.cleaned_data.get("restrictions_topics") or "Нет").strip()
        profile.restrictions_schedule = (self.cleaned_data.get("restrictions_schedule") or "Нет").strip()

        profile.fso_status = self.cleaned_data.get("fso_status") or ""
        profile.own_equipment = (self.cleaned_data.get("own_equipment") or "Нет").strip()

        profile.education = self.cleaned_data.get("education") or ""
        profile.additional_skills = (self.cleaned_data.get("additional_skills") or "").strip()

        profile.resume = self.cleaned_data.get("resume")
        profile.photo = self.cleaned_data.get("photo")

        profile.save()
        return user