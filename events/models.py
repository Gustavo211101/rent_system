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
    STATUS_PLANNED = "planned"
    STATUS_CONFIRMED = "confirmed"
    STATUS_LOADING = "loading"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_FINISHED = "finished"
    STATUS_CANCELLED = "cancelled"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Черновик"),
        (STATUS_PLANNED, "Запланировано"),
        (STATUS_CONFIRMED, "Подтверждено"),
        (STATUS_LOADING, "Погрузка"),
        (STATUS_IN_PROGRESS, "В работе"),
        (STATUS_FINISHED, "Завершено"),
        (STATUS_CANCELLED, "Отменено"),
        (STATUS_CLOSED, "Закрыто"),
    )

    # Статусы, которые считаем “активными” для календаря/фильтров
    STATUS_ACTIVE = (
        STATUS_PLANNED,
        STATUS_CONFIRMED,
        STATUS_LOADING,
        STATUS_IN_PROGRESS,
        STATUS_FINISHED,
    )

    # Разрешённые переходы статусов (workflow)
    STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
        STATUS_DRAFT: (STATUS_PLANNED, STATUS_CANCELLED),
        STATUS_PLANNED: (STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_DRAFT),
        STATUS_CONFIRMED: (STATUS_LOADING, STATUS_CANCELLED, STATUS_PLANNED),
        STATUS_LOADING: (STATUS_IN_PROGRESS,),
        STATUS_IN_PROGRESS: (STATUS_FINISHED,),
        STATUS_FINISHED: (STATUS_CLOSED,),
        STATUS_CANCELLED: (),
        STATUS_CLOSED: (),
    }

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

    def has_active_stock_issues(self) -> bool:
        return self.stock_issues.filter(returned_at__isnull=True).exists()

    def allowed_next_statuses(self) -> tuple[str, ...]:
        return self.STATUS_TRANSITIONS.get(self.status, ())

    def can_set_status(self, new_status: str) -> tuple[bool, str]:
        """Возвращает (ok, reason)."""
        if new_status == self.status:
            return True, ""
        if new_status not in dict(self.STATUS_CHOICES):
            return False, "Некорректный статус."
        allowed = set(self.allowed_next_statuses())
        if new_status not in allowed:
            return False, "Недопустимый переход статуса."
        # Нельзя отменять, если уже есть выданные (не возвращённые) инвентарники
        if new_status == self.STATUS_CANCELLED and self.has_active_stock_issues():
            return False, "Нельзя отменить мероприятие: сначала оформите возврат выданного оборудования."
        return True, ""

    def is_ready_to_close(self) -> tuple[bool, str]:
        """Условия закрытия: нет невозвращённого оборудования и по брони всё было выдано."""
        if self.has_active_stock_issues():
            return False, "Нельзя закрыть: есть невозвращённые инвентарники."

        # Проверим, что выдача (фактические сканы) покрывает бронь по типам
        from django.apps import apps
        from django.db.models import Count

        EventStockReservation = apps.get_model("events", "EventStockReservation")
        EventStockIssue = apps.get_model("events", "EventStockIssue")

        issued_counts = (
            EventStockIssue.objects.filter(event=self)
            .values("item__equipment_type_id")
            .annotate(c=Count("id"))
        )
        issued_map = {row["item__equipment_type_id"]: int(row["c"] or 0) for row in issued_counts}

        for r in EventStockReservation.objects.filter(event=self):
            if issued_map.get(r.equipment_type_id, 0) < r.quantity:
                return False, "Нельзя закрыть: не всё оборудование было выдано по брони."

        return True, ""


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
        qs = EventStockReservation.objects.select_related("event").filter(equipment_type=equipment_type)
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

    def __str__(self):
        return f"{self.event} — {self.item.inventory_number}"

    @property
    def is_returned(self) -> bool:
        return bool(self.returned_at)