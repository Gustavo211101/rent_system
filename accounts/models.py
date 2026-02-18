from __future__ import annotations

import secrets
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser


def generate_invite_token() -> str:
    # дает строку ~43-44 символа, безопасно для URL
    return secrets.token_urlsafe(32)


class User(AbstractUser):
    phone = models.CharField("Телефон", max_length=30, blank=True, default="")
    patronymic = models.CharField("Отчество", max_length=150, blank=True, default="")

    class Meta(AbstractUser.Meta):
        permissions = [
            ("manage_staff", "Can manage staff (users/roles)"),
        ]

    def get_full_name(self) -> str:
        # Фамилия Имя Отчество (если есть)
        parts = [self.last_name, self.first_name, self.patronymic]
        return " ".join([p.strip() for p in parts if p and p.strip()]).strip() or self.username

    def __str__(self) -> str:
        return self.get_full_name()


class Profile(models.Model):
    """Расширенная карточка сотрудника (анкета)"""

    class Gender(models.TextChoices):
        MALE = "male", "Мужской"
        FEMALE = "female", "Женский"
        OTHER = "other", "Другое"

    class YesNoMaybe(models.TextChoices):
        YES = "yes", "Да"
        NO = "no", "Нет"
        LIMITED = "limited", "Ограниченно"

    class Citizenship(models.TextChoices):
        RU = "RU", "РФ"
        OTHER = "OTHER", "Другое"

    class FSOStatus(models.TextChoices):
        YES = "yes", "Да"
        NO = "no", "Нет"
        IN_PROGRESS = "in_progress", "В процессе"
        NA = "na", "Не требуется/не знаю"

    class Education(models.TextChoices):
        HIGHER_FULL = "higher_full", "Высшее-полное"
        HIGHER = "higher", "Высшее"
        SECONDARY = "secondary", "Среднее"
        OTHER = "other", "Другое"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")

    last_name_lat = models.CharField("Фамилия латиницей", max_length=150, blank=True, default="")
    first_name_lat = models.CharField("Имя латиницей", max_length=150, blank=True, default="")
    patronymic_lat = models.CharField("Отчество латиницей", max_length=150, blank=True, default="")

    gender = models.CharField("Пол", max_length=20, choices=Gender.choices, blank=True, default="")
    citizenship = models.CharField(
        "Гражданство", max_length=20, choices=Citizenship.choices, blank=True, default=Citizenship.RU
    )
    telegram = models.CharField("Телеграм", max_length=150, blank=True, default="")

    qualification = models.CharField("Квалификация, навыки", max_length=255, blank=True, default="")
    travel_ready = models.CharField(
        "Готовность к командировкам", max_length=20, choices=YesNoMaybe.choices, blank=True, default=""
    )
    quarantine_ready = models.CharField(
        "Готовность к карантину", max_length=20, choices=YesNoMaybe.choices, blank=True, default=""
    )

    restrictions_companies = models.CharField(
        "Ограничения по работе с компаниями", max_length=255, blank=True, default="Нет"
    )
    restrictions_topics = models.CharField(
        "Ограничения на участие в проектах с определённой тематикой", max_length=255, blank=True, default="Нет"
    )
    restrictions_schedule = models.CharField(
        "Ограничения по графику работы", max_length=255, blank=True, default="Нет"
    )

    fso_status = models.CharField(
        "Прохождение ФСО", max_length=30, choices=FSOStatus.choices, blank=True, default=""
    )
    own_equipment = models.CharField("Наличие собственного оборудования", max_length=255, blank=True, default="Нет")

    education = models.CharField("Образование", max_length=30, choices=Education.choices, blank=True, default="")
    additional_skills = models.TextField("Дополнительные навыки", blank=True, default="")

    resume = models.FileField("Резюме", upload_to="staff/resumes/", blank=True, null=True)
    photo = models.ImageField("Фото", upload_to="staff/photos/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user_id})"


class StaffInvite(models.Model):
    # ✅ ВАЖНО: строковый токен, чтобы принимал token_urlsafe()
    token = models.CharField(max_length=128, unique=True, default=generate_invite_token, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="staff_invites_created"
    )
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="staff_invites_used"
    )

    @property
    def is_used(self):
        return self.used_at is not None

    def mark_used(self, user):
        self.used_at = timezone.now()
        self.used_by = user
        self.save(update_fields=["used_at", "used_by"])