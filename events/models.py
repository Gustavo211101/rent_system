from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import Group

from inventory.models import Equipment, StockEquipmentType, StockEquipmentItem

User = settings.AUTH_USER_MODEL


class Event(models.Model):
    class Meta:
        permissions = [
            ("edit_event_card", "Can edit event card (dates/status/etc)"),
            ("edit_event_equipment", "Can edit event equipment (own/rented)"),
        ]

    STATUS_DRAFT = "draft"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Черновик"),
        (STATUS_CONFIRMED, "Подтверждено"),
        (STATUS_CANCELLED, "Отменено"),
        (STATUS_CLOSED, "Закрыто"),
    )

    name = models.CharField(max_length=200)

    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    client = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)

    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="events",
    )

    # Старший инженер
    s_engineer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="senior_events",
    )

    # Инженеры
    engineers = models.ManyToManyField(
        User,
        blank=True,
        related_name="engineer_events",
    )

    # Заметки менеджера
    notes = models.TextField(blank=True, default="")

    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
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


class EventRoleSlot(models.Model):
    """
    Дополнительные роли на мероприятии (только по необходимости).
    Пример: "Водитель", "Фотограф", "Свет", "Звук" и т.п.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="role_slots")
    role = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="event_role_slots")
    users = models.ManyToManyField(User, blank=True, related_name="event_extra_roles")

    class Meta:
        unique_together = ("event", "role")
        ordering = ["role__name", "id"]

    def __str__(self):
        return f"{self.event} — {self.role.name}"


class EventEquipment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="equipment_items")
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name="event_items")
    quantity = models.PositiveIntegerField()

    class Meta:
        unique_together = ("event", "equipment")

    def __str__(self):
        return f"{self.equipment.name} × {self.quantity}"


class EventRentedEquipment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rented_items")
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name="rented_event_items")
    quantity = models.PositiveIntegerField()

    class Meta:
        unique_together = ("event", "equipment")

    def __str__(self):
        return f"Аренда: {self.equipment.name} × {self.quantity}"


class EventStockReservation(models.Model):
    """Фаза 1: бронь оборудования со склада по ТИПАМ и количеству на даты мероприятия.

    В момент планирования на мероприятии храним только:
      - какой тип оборудования нужен
      - какое количество бронируем

    Конкретные инвентарники привязываются позже на этапе погрузки (Фаза 2).
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="stock_reservations")
    equipment_type = models.ForeignKey(StockEquipmentType, on_delete=models.PROTECT, related_name="event_reservations")
    quantity = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_stock_reservations",
    )

    class Meta:
        unique_together = ("event", "equipment_type")
        ordering = ["equipment_type__category__name", "equipment_type__subcategory__name", "equipment_type__name", "id"]

    def __str__(self):
        return f"{self.event} — {self.equipment_type.name} × {self.quantity}"

    @staticmethod
    def available_for_dates(equipment_type: StockEquipmentType, start_date, end_date, exclude_event_id: int | None = None) -> int:
        """Сколько единиц данного типа доступно на даты (с учётом ремонтов и чужих броней)."""
        # Общее доступное физически: всё, кроме ремонта
        total_physical = StockEquipmentItem.objects.filter(
            equipment_type=equipment_type
        ).exclude(status=StockEquipmentItem.STATUS_REPAIR).count()

        # Сумма броней на пересекающиеся даты (кроме текущего события)
        # Важно: учитываем только «активные» события, иначе бронь будет «залипать» навсегда.
        qs = (
            EventStockReservation.objects.select_related("event")
            .filter(equipment_type=equipment_type)
            .filter(event__is_deleted=False)
            .filter(event__status__in=[Event.STATUS_DRAFT, Event.STATUS_CONFIRMED])
        )
        if exclude_event_id:
            qs = qs.exclude(event_id=exclude_event_id)

        qs = qs.filter(event__start_date__lte=end_date, event__end_date__gte=start_date)

        reserved = qs.aggregate(models.Sum("quantity")).get("quantity__sum") or 0

        return max(0, total_physical - reserved)


class EventStockIssue(models.Model):
    """Фаза 2: фактическая выдача (погрузка) — привязка конкретных инвентарников к мероприятию.

    Создаётся при сканировании инвентарника на погрузке.
    Возврат (returned_*) будет реализован следующим шагом.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="stock_issues")
    item = models.ForeignKey(StockEquipmentItem, on_delete=models.PROTECT, related_name="event_issues")

    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_stock_items",
    )

    returned_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="returned_stock_items",
    )

    class Meta:
        ordering = ["-issued_at", "-id"]
        constraints = [
            # Один и тот же инвентарник не может быть выдан дважды в рамках одного мероприятия.
            models.UniqueConstraint(
                fields=["event", "item"],
                condition=models.Q(returned_at__isnull=True),
                name="uniq_event_stock_issue_active_event_item",
            ),
            # Один и тот же инвентарник не может быть одновременно "активно" выдан в разные мероприятия.
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(returned_at__isnull=True),
                name="uniq_event_stock_issue_active_item",
            ),
        ]

    def __str__(self):
        return f"{self.event} — {self.item.inventory_number}"

    @property
    def is_returned(self) -> bool:
        return bool(self.returned_at)