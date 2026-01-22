from django.db import models
from django.db.models import Sum
from django.utils import timezone


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

    def in_repair_quantity(self, start, end):
        """Сколько единиц находится в ремонте и пересекает период [start, end]."""
        return (
            self.repairs
            .filter(status=EquipmentRepair.STATUS_IN_REPAIR, start_date__lte=end)
            .filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=start))
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )

    def available_quantity(self, start, end):
        available = self.quantity_total - self.reserved_quantity(start, end) - self.in_repair_quantity(start, end)
        if available < 0:
            available = 0
        return available


class EquipmentRepair(models.Model):
    STATUS_IN_REPAIR = "in_repair"
    STATUS_RETURNED = "returned"

    STATUS_CHOICES = (
        (STATUS_IN_REPAIR, "В ремонте"),
        (STATUS_RETURNED, "Возвращено"),
    )

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="repairs")
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_REPAIR)

    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)

    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.equipment.name} × {self.quantity} ({self.get_status_display()})"
