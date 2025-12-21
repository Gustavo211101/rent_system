from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from inventory.models import Equipment

User = settings.AUTH_USER_MODEL


class Event(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_IN_RENT = 'in_rent'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Черновик'),
        (STATUS_CONFIRMED, 'Подтверждено'),
        (STATUS_IN_RENT, 'В прокате'),
        (STATUS_CLOSED, 'Закрыто'),
    )

    name = models.CharField(max_length=200)

    # теперь только даты, без времени
    start_date = models.DateField()
    end_date = models.DateField()

    client = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)

    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='events'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    equipment_tbd = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_closed(self):
        return self.status == self.STATUS_CLOSED

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("Дата окончания не может быть раньше даты начала")

    def __str__(self):
        if self.start_date == self.end_date:
            return f"{self.name} ({self.start_date:%d.%m.%Y})"
        return f"{self.name} ({self.start_date:%d.%m.%Y}–{self.end_date:%d.%m.%Y})"


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
        # Проверка доступности по ДАТАМ
        available = self.equipment.available_quantity(
            self.event.start_date,
            self.event.end_date
        )

        if self.pk:
            old_quantity = EventEquipment.objects.get(pk=self.pk).quantity
            available += old_quantity

        if self.quantity > available:
            raise ValidationError(f"Недостаточно оборудования. Доступно: {available}")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class EventRentedEquipment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='rented_items')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='rented_event_items')
    quantity = models.PositiveIntegerField()

    class Meta:
        unique_together = ('event', 'equipment')

    def __str__(self):
        return f"{self.equipment.name} (в аренду) × {self.quantity}"
