from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"

    ACTION_CHOICES = (
        (ACTION_CREATE, "Создание"),
        (ACTION_UPDATE, "Изменение"),
        (ACTION_DELETE, "Удаление"),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Кто сделал",
    )

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=120)         # например "Equipment"
    entity_id = models.CharField(max_length=64, blank=True)  # id как строка (на всякий)
    entity_repr = models.CharField(max_length=255, blank=True)

    message = models.TextField(blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def str(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.action} {self.entity_type}#{self.entity_id}"