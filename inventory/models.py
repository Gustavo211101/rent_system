from django.db import models
from django.db.models import Sum


class EquipmentCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Equipment(models.Model):
    class Meta:
        permissions = [
            ("manage_inventory", "Can manage inventory"),
        ]

    STATUS_CHOICES = (
        ("available", "Доступно"),
        ("rented", "В прокате"),
        ("broken", "Неисправно"),
    )

    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.PROTECT,
        related_name="equipment",
    )
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    quantity_total = models.PositiveIntegerField()
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.quantity_total})"

    def reserved_quantity(self, start, end):
        """
        start/end — даты (DateField).
        Пересечение диапазонов дат (включительно):
            event.start_date <= end AND event.end_date >= start
        """
        return (
            self.event_items
            .filter(event__start_date__lte=end, event__end_date__gte=start)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )

    def available_quantity(self, start, end):
        available = self.quantity_total - self.reserved_quantity(start, end)
        if available < 0:
            available = 0
        return available
