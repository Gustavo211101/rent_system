from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.conf import settings


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


# =========================
# Warehouse (per-item) stock
# =========================
# Эти модели добавлены для будущего "складского" учёта по единицам (инвентарникам).
# Они НЕ используются текущими экранами/логикой проката, поэтому безопасны для внедрения поэтапно.

class StockCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Категория склада"
        verbose_name_plural = "Категории склада"
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class StockSubcategory(models.Model):
    category = models.ForeignKey(StockCategory, on_delete=models.PROTECT, related_name="subcategories")
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Подкатегория склада"
        verbose_name_plural = "Подкатегории склада"
        unique_together = ("category", "name")
        ordering = ["category__name", "name", "id"]

    def __str__(self):
        return f"{self.category.name} / {self.name}"


class StockEquipmentType(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(StockCategory, on_delete=models.PROTECT)
    subcategory = models.ForeignKey(
        StockSubcategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    power_w = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Потребляемая мощность (Вт)"
    )

    dimensions_mm = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Габариты (мм)"
    )

    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Вес (кг)"
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # ТТХ — храним на уровне ТИПА, а не конкретной единицы.
    weight_kg = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    width_mm = models.PositiveIntegerField(null=True, blank=True)
    height_mm = models.PositiveIntegerField(null=True, blank=True)
    depth_mm = models.PositiveIntegerField(null=True, blank=True)
    power_watt = models.PositiveIntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Тип оборудования склада"
        verbose_name_plural = "Типы оборудования склада"
        unique_together = ("category", "subcategory", "name")
        ordering = ["category__name", "subcategory__name", "name", "id"]

    def __str__(self):
        return self.name

    @property
    def total_count(self) -> int:
        return self.items.count()

    @property
    def available_count(self) -> int:
        return self.items.filter(status=StockEquipmentItem.STATUS_STORAGE).count()

    @property
    def in_repair_count(self) -> int:
        return self.items.filter(status=StockEquipmentItem.STATUS_REPAIR).count()


class StockEquipmentItem(models.Model):
    STATUS_STORAGE = "storage"
    STATUS_EVENT = "event"
    STATUS_REPAIR = "repair"

    STATUS_CHOICES = (
        (STATUS_STORAGE, "На складе"),
        (STATUS_EVENT, "На мероприятии"),
        (STATUS_REPAIR, "В ремонте"),
    )

    equipment_type = models.ForeignKey(
        StockEquipmentType,
        on_delete=models.PROTECT,
        related_name="items",
    )
    inventory_number = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_STORAGE,
    )

    comment = models.CharField(max_length=255, blank=True)
    photo = models.FileField(upload_to="equipment_photos/", blank=True, null=True)

    # Комплект: связанные позиции (например, компьютер + адаптеры).
    # Нужен для импорта из Excel и дальнейшего автодобавления при сканировании на мероприятие.
    kit_items = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="kit_parents",
        verbose_name="Комплект",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Единица оборудования"
        verbose_name_plural = "Единицы оборудования"
        ordering = ["equipment_type__name", "inventory_number", "id"]

    def __str__(self):
        return f"{self.equipment_type.name} ({self.inventory_number})"


class StockRepair(models.Model):
    equipment_item = models.ForeignKey(StockEquipmentItem, on_delete=models.CASCADE, related_name="repairs")

    # Причина обязательна.
    reason = models.TextField()
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # Заметка при возврате на склад (обязательна по UX, но храним как optional,
    # а обязательность обеспечиваем на уровне формы/вьюхи).
    close_note = models.TextField(blank=True)

    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="opened_stock_repairs"
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="closed_stock_repairs"
    )

    class Meta:
        verbose_name = "Ремонт (склад)"
        verbose_name_plural = "Ремонты (склад)"
        ordering = ["-opened_at", "-id"]

    def __str__(self):
        return f"{self.equipment_item.inventory_number}: {self.reason[:40]}"