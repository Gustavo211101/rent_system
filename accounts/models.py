from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Кастомный пользователь.
    """
    phone = models.CharField("Телефон", max_length=30, blank=True, default="")

    class Meta(AbstractUser.Meta):
        permissions = [
            ("manage_staff", "Can manage staff (users/roles)"),
        ]


class StaffInvite(models.Model):
    """
    Одноразовая ссылка для регистрации сотрудника.
    """
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_staff_invites",
    )

    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="used_staff_invites",
    )

    def mark_used(self, user):
        self.is_used = True
        self.used_at = timezone.now()
        self.used_by = user
        self.save(update_fields=["is_used", "used_at", "used_by"])

    def __str__(self):
        status = "used" if self.is_used else "new"
        return f"Invite({status}) {self.token[:8]}"
