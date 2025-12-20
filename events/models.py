from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from inventory.models import Equipment

User = settings.AUTH_USER_MODEL


class Event(models.Model):
    name = models.CharField(max_length=200)

    all_day = models.BooleanField(
        default=False,
        verbose_name='Весь день'
    )

    # Если True — мы считаем, что оборудование ещё не подобрано
    equipment_tbd = models.BooleanField(
        default=True,
        verbose_name='Оборудование выберу позже'
    )

    date_start = models.DateTimeField()
    date_end = models.DateTimeField()

    client = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)

    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='events'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.all_day and self.date_start and self.date_end:
            self.date_start = self.date_start.replace(hour=0, minute=0, second=0, microsecond=0)
            self.date_end = self.date_end.replace(hour=23, minute=59, second=59, microsecond=0)

        if self.date_start and self.date_end and self.date_end <= self.date_start:
            raise ValidationError('Дата окончания должна быть позже даты начала')

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
