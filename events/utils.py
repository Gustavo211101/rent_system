# events/utils.py
from __future__ import annotations

from datetime import date

from django.db.models import Sum

from .models import Event, EventEquipment, EventRentedEquipment


def auto_close_past_events():
    today = date.today()
    Event.objects.filter(end_date__lt=today).exclude(status="closed").update(status="closed")


def calculate_shortages(event: Event):
    """
    Возвращает список словарей по оборудованию, где не хватает количества, с учетом:
    - "своего" наличия (quantity_total - резервы в других мероприятиях на те же даты)
    - уже добавленной аренды (rented_items)
    Формат под твой шаблон:
      {
        "equipment": <Equipment>,
        "required": int,
        "available_own": int,
        "rented": int,
        "shortage": int,
      }
    """
    # Мягко защитимся, если даты пустые (на всякий случай)
    if not event.start_date or not event.end_date:
        return []

    shortages = []

    # Собранная аренда по текущему мероприятию (чтобы быстро суммировать)
    rented_map = {}
    rented_qs = (
        EventRentedEquipment.objects.filter(event=event)
        .values("equipment_id")
        .annotate(total=Sum("quantity"))
    )
    for row in rented_qs:
        rented_map[row["equipment_id"]] = int(row["total"] or 0)

    # Требуемое своё оборудование
    items = (
        EventEquipment.objects
        .filter(event=event)
        .select_related("equipment")
    )

    for item in items:
        eq = item.equipment
        required = int(item.quantity or 0)

        # Резерв "другими" мероприятиями на тот же период
        reserved_other = (
            EventEquipment.objects
            .filter(
                equipment=eq,
                event__start_date__lte=event.end_date,
                event__end_date__gte=event.start_date,
            )
            .exclude(event=event)
            .aggregate(total=Sum("quantity"))["total"] or 0
        )
        reserved_other = int(reserved_other)

        available_own = max(int(eq.quantity_total) - reserved_other, 0)

        rented = int(rented_map.get(eq.id, 0))

        shortage = max(required - (available_own + rented), 0)
        if shortage > 0:
            shortages.append(
                {
                    "equipment": eq,
                    "required": required,
                    "available_own": available_own,
                    "rented": rented,
                    "shortage": shortage,
                }
            )

    return shortages
