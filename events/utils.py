from __future__ import annotations

from datetime import date

from django.db.models import Sum

from .models import Event, EventEquipment, EventRentedEquipment


def auto_close_past_events():
    """
    Автозакрытие прошедших мероприятий:
    если end_date < today и статус не closed/cancelled -> closed
    """
    today = date.today()
    Event.objects.filter(end_date__lt=today).exclude(status__in=["closed", "cancelled"]).update(status="closed")


def calculate_shortages(event: Event):
    """
    ЕДИНЫЙ расчёт нехватки для:
    - карточки мероприятия
    - страницы аренды (добавить аренду)
    - подсветки проблем в календаре

    Формула:
      reserved_other = брони ДРУГИХ мероприятий на те же даты
      available_own = quantity_total - reserved_other
      shortage = max(0, required - (available_own + rented))
    """
    start = event.start_date
    end = event.end_date or event.start_date

    # Нужно на мероприятие (текущее)
    required_rows = (
        EventEquipment.objects
        .filter(event=event)
        .values("equipment_id")
        .annotate(required=Sum("quantity"))
    )
    required_map = {r["equipment_id"]: int(r["required"] or 0) for r in required_rows}

    if not required_map:
        return []

    # Уже в аренде (текущее)
    rented_rows = (
        EventRentedEquipment.objects
        .filter(event=event)
        .values("equipment_id")
        .annotate(rented=Sum("quantity"))
    )
    rented_map = {r["equipment_id"]: int(r["rented"] or 0) for r in rented_rows}

    # Забронировано ДРУГИМИ мероприятиями (важно: exclude(event=event))
    reserved_other_rows = (
        EventEquipment.objects
        .filter(
            event__start_date__lte=end,
            event__end_date__gte=start,
            equipment_id__in=required_map.keys(),
        )
        .exclude(event=event)
        .values("equipment_id")
        .annotate(reserved=Sum("quantity"))
    )
    reserved_other_map = {r["equipment_id"]: int(r["reserved"] or 0) for r in reserved_other_rows}

    from inventory.models import Equipment  # локально, чтобы избежать циклов

    equipments = Equipment.objects.filter(id__in=required_map.keys())
    eq_map = {e.id: e for e in equipments}

    result = []
    for eq_id, required in required_map.items():
        eq = eq_map.get(eq_id)
        if not eq:
            continue

        reserved_other = reserved_other_map.get(eq_id, 0)
        available_own = int(eq.quantity_total) - int(reserved_other)
        if available_own < 0:
            available_own = 0

        rented = rented_map.get(eq_id, 0)

        shortage = required - (available_own + rented)
        if shortage < 0:
            shortage = 0

        if shortage > 0:
            result.append({
                "equipment": eq,
                "required": required,
                "available_own": available_own,
                "rented": rented,
                "shortage": shortage,
            })

    result.sort(key=lambda x: x["shortage"], reverse=True)
    return result
