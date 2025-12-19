from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from inventory.models import Equipment

User = settings.AUTH_USER_MODEL


class Event(models.Model):
    name = models.CharField(max_length=200)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()

    client = models.CharField(
        max_length=200,
        blank=True
    )
    location = models.CharField(
        max_length=200,
        blank=True
    )

    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='events'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.date_start:%d.%m.%Y})"


class EventEquipment(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='equipment_items'
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        related_name='event_items'
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        unique_together = ('event', 'equipment')

    def __str__(self):
        return f"{self.equipment.name} × {self.quantity}"

    def clean(self):
        available = self.equipment.available_quantity(
            self.event.date_start,
            self.event.date_end
        )

        if self.pk:
            old_quantity = EventEquipment.objects.get(pk=self.pk).quantity
            available += old_quantity

        if self.quantity > available:
            raise ValidationError(
                f"Недостаточно оборудования. Доступно: {available}"
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
