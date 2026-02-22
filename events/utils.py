from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Sum

from .models import Event, EventEquipment, EventRentedEquipment



def purge_soft_deleted_events(days: int = 30) -> int:
    """Удаляет из БД мероприятия, которые были soft-deleted более `days` дней назад."""
    cutoff = date.today() - timedelta(days=days)
    qs = Event.objects.filter(is_deleted=True, deleted_at__isnull=False, deleted_at__lt=cutoff)
    count = qs.count()
    qs.delete()
    return count



def auto_close_past_events() -> int:
    """
    Авто-статус прошедших мероприятий:
    - если end_date < today и есть невозвращённые инвентарники -> problem
    - если end_date < today и всё возвращено -> closed
    Возвращает количество изменённых записей (примерно).
    """
    today = date.today()
    qs = Event.objects.filter(end_date__lt=today, is_deleted=False)

    # 1) Сначала отметим проблемные (есть невозвращённые)
    problem_qs = qs.filter(stock_issues__returned_at__isnull=True).exclude(status=Event.STATUS_PROBLEM)
    n_problem = problem_qs.update(status=Event.STATUS_PROBLEM)

    # 2) Остальные прошедшие без активных выдач -> closed
    closed_qs = qs.exclude(stock_issues__returned_at__isnull=True).exclude(status=Event.STATUS_CLOSED)
    n_closed = closed_qs.update(status=Event.STATUS_CLOSED)

    return int(n_problem or 0) + int(n_closed or 0)


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


def find_personnel_conflicts(*, user_ids: list[int], start_date: date, end_date: date, exclude_event_id: int | None = None):
    """Возвращает словарь {user_id: [events...]} для пересекающихся мероприятий.
    Не блокирует сохранение — используется для предупреждений.
    """
    from django.db.models import Q

    if not user_ids:
        return {}

    qs = (
        Event.objects.filter(is_deleted=False)
        .exclude(status__in=[Event.STATUS_PROBLEM, Event.STATUS_CLOSED])
        .filter(start_date__lte=end_date, end_date__gte=start_date)
    )
    if exclude_event_id:
        qs = qs.exclude(id=exclude_event_id)

    conflicts: dict[int, list[Event]] = {uid: [] for uid in user_ids}
    for uid in user_ids:
        u_q = (
            Q(responsible_id=uid)
            | Q(s_engineer_id=uid)
            | Q(engineers__id=uid)
            | Q(role_slots__users__id=uid)
        )
        evs = list(qs.filter(u_q).distinct().order_by("start_date", "id")[:50])
        if evs:
            conflicts[uid] = evs

    # убрать пустые
    return {uid: evs for uid, evs in conflicts.items() if evs}
