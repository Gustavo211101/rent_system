from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from inventory.models import Equipment


User = settings.AUTH_USER_MODEL


class Event(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Черновик'),
        (STATUS_CONFIRMED, 'Подтверждено'),
        (STATUS_CANCELLED, 'Отменено'),
        (STATUS_CLOSED, 'Закрыто'),
    )

    name = models.CharField(max_length=200)

    # только дни
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    client = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)

    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='events'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # end_date по умолчанию = start_date
        if not self.end_date:
            self.end_date = self.start_date

        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("Дата окончания не может быть раньше даты начала.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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
        # проверка на доступность в пересечении дат
        start = self.event.start_date
        end = self.event.end_date

        available = self.equipment.available_quantity(start, end)

        # если редактируем существующую строку — возвращаем старое количество в доступность
        if self.pk:
            old_quantity = EventEquipment.objects.get(pk=self.pk).quantity
            available += old_quantity

        # мы разрешаем добавлять больше, чем доступно (ты просил),
        # но ValidationError не бросаем — нехватку покажем как предупреждение.
        # Поэтому clean здесь больше не ограничивает.
        # (оставляем как точку расширения)
        return

    def save(self, *args, **kwargs):
        # не full_clean, чтобы не блокировать “не хватает”
        super().save(*args, **kwargs)


class EventRentedEquipment(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='rented_items'
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        related_name='rented_event_items'
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        unique_together = ('event', 'equipment')

    def __str__(self):
        return f"Аренда: {self.equipment.name} × {self.quantity}"
