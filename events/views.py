from __future__ import annotations

import calendar as pycalendar
from collections import defaultdict
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import can_edit_event_card, can_edit_event_equipment

# audit логирование (если есть)
try:
    from audit.utils import log_action  # type: ignore
except Exception:  # pragma: no cover
    def log_action(*args, **kwargs):  # type: ignore
        return None

from .forms import EventEquipmentForm, EventForm, EventRentedEquipmentForm
from .models import Event, EventEquipment, EventRentedEquipment


def _safe_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _parse_year_month(request: HttpRequest) -> tuple[int, int]:
    today = timezone.localdate()
    year = _safe_int(request.GET.get("year"), today.year)
    month = _safe_int(request.GET.get("month"), today.month)
    if month < 1:
        month = 1
    if month > 12:
        month = 12
    if year < 1970:
        year = 1970
    if year > 2100:
        year = 2100
    return year, month


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last_day = pycalendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    return first, last


def _calculate_shortages(event: Event):
    """
    Мягкий расчёт нехватки, чтобы не ронять карточку/календарь.
    Возвращает список для шаблона (или [] если что-то не так).
    """
    try:
        start = event.start_date
        end = event.end_date
        required_rows = (
            EventEquipment.objects
            .filter(event=event)
            .select_related("equipment")
        )
        rented_rows = (
            EventRentedEquipment.objects
            .filter(event=event)
            .select_related("equipment")
        )
    except Exception:
        return []

    rented_map: dict[int, int] = {}
    for r in rented_rows:
        try:
            rented_map[r.equipment_id] = rented_map.get(r.equipment_id, 0) + int(r.quantity or 0)
        except Exception:
            pass

    out = []
    for row in required_rows:
        eq = row.equipment
        required = int(getattr(row, "quantity", 0) or 0)

        available_own = 0
        try:
            # inventory.models.Equipment.available_quantity(start,end)
            available_own = int(eq.available_quantity(start, end))  # type: ignore
        except Exception:
            try:
                available_own = int(getattr(eq, "quantity_total", 0) or 0)
            except Exception:
                available_own = 0

        rented = rented_map.get(row.equipment_id, 0)
        shortage = required - (available_own + rented)
        if shortage > 0:
            out.append(
                {
                    "equipment": eq,
                    "required": required,
                    "available_own": available_own,
                    "rented": rented,
                    "shortage": shortage,
                }
            )
    return out


def _calendar_filter_label(value: str) -> str:
    mapping = {
        "all": "Все",
        "confirmed": "Только подтверждённые",
        "mine": "Только мои",
    }
    return mapping.get(value, "Все")


@login_required
def calendar_view(request: HttpRequest) -> HttpResponse:
    """
    1) Листание месяцев (?year=...&month=...)
    2) Фильтр: all / confirmed / mine
    3) Многодневные события раскладываются по дням + флаги start/mid/end для "полоски"
    """
    year, month = _parse_year_month(request)
    month_start, month_end = _month_bounds(year, month)

    cal_filter = (request.GET.get("filter") or "all").strip()
    if cal_filter not in {"all", "confirmed", "mine"}:
        cal_filter = "all"

    qs = (
        Event.objects
        .filter(start_date__lte=month_end, end_date__gte=month_start)
        .select_related("responsible")
        .order_by("start_date", "id")
    )

    if cal_filter == "confirmed":
        qs = qs.filter(status="confirmed")
    elif cal_filter == "mine":
        qs = qs.filter(responsible=request.user)

    # день -> список элементов {event, is_start, is_end, is_single, has_problem}
    events_by_day: dict[date, list[dict]] = defaultdict(list)

    # Чтобы не считать shortages дорого, делаем только признак "есть проблема"
    # (и только если надо показать обводку). Мягко.
    event_problem: dict[int, bool] = {}
    for e in qs:
        try:
            event_problem[e.id] = bool(_calculate_shortages(e))
        except Exception:
            event_problem[e.id] = False

    for e in qs:
        start = max(e.start_date, month_start)
        end = min(e.end_date, month_end)

        d = start
        while d <= end:
            is_start = (d == e.start_date)
            is_end = (d == e.end_date)
            is_single = (e.start_date == e.end_date)

            # если событие началось до месяца — в текущем месяце первый день считаем как "start" для полоски
            if e.start_date < month_start and d == month_start:
                is_start = True
            # если событие заканчивается после месяца — последний день месяца считаем как "end"
            if e.end_date > month_end and d == month_end:
                is_end = True

            events_by_day[d].append({
                "event": e,
                "is_start": is_start,
                "is_end": is_end,
                "is_single": is_single,
                "has_problem": event_problem.get(e.id, False),
            })
            d = d + timedelta(days=1)

    # в каждом дне отсортируем по времени/названию (стабильно)
    for day_key in events_by_day:
        events_by_day[day_key].sort(key=lambda x: (x["event"].start_date, x["event"].id))

    month_days = list(pycalendar.Calendar(firstweekday=0).monthdatescalendar(year, month))

    ctx = {
        "year": year,
        "month": month,
        "month_name": pycalendar.month_name[month],
        "month_days": month_days,
        "events_by_day": dict(events_by_day),

        "filter": cal_filter,
        "filter_label": _calendar_filter_label(cal_filter),
        "can_create_event": can_edit_event_card(request.user),  # для клика по дню
    }
    return render(request, "events/calendar.html", ctx)


@login_required
def event_list_view(request: HttpRequest) -> HttpResponse:
    qs = Event.objects.all().select_related("responsible").order_by("-start_date", "-id")
    ctx = {
        "events": qs,
        "can_create_event": can_edit_event_card(request.user),
    }
    return render(request, "events/event_list.html", ctx)


@login_required
def event_detail_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)

    equipment_items = (
        EventEquipment.objects
        .filter(event=event)
        .select_related("equipment")
        .order_by("equipment__name")
    )

    rented_items = (
        EventRentedEquipment.objects
        .filter(event=event)
        .select_related("equipment")
        .order_by("equipment__name")
    )

    ctx = {
        "event": event,
        "equipment_items": equipment_items,
        "rented_items": rented_items,
        "shortages": _calculate_shortages(event),
        "can_modify": can_edit_event_card(request.user),
        "can_edit_equipment": can_edit_event_equipment(request.user),
    }
    return render(request, "events/event_detail.html", ctx)


@login_required
def event_create_view(request):
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    # initial данные (из календаря / модалки)
    initial = {}

    start_date = (request.GET.get("start_date") or "").strip()
    end_date = (request.GET.get("end_date") or "").strip()
    name = (request.GET.get("name") or "").strip()

    if start_date:
        initial["start_date"] = start_date
        initial["end_date"] = end_date or start_date

    if name:
        initial["name"] = name

    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save()
            log_action(
                user=request.user,
                action="create",
                obj=event,
                details="Создано мероприятие",
            )
            messages.success(request, "Мероприятие создано.")
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventForm(initial=initial)

    return render(
        request,
        "events/event_form.html",
        {
            "form": form,
            "title": "Создать мероприятие",
        },
    )

@login_required
def event_update_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save()
            log_action(user=request.user, action="update", obj=event, details="Изменено мероприятие")
            messages.success(request, "Изменения сохранены.")
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventForm(instance=event)

    return render(request, "events/event_form.html", {"form": form, "title": "Редактировать мероприятие"})


@login_required
def event_set_status_view(request: HttpRequest, event_id: int, status: str) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    allowed = {"draft", "confirmed", "cancelled", "closed"}
    if status not in allowed:
        messages.error(request, "Некорректный статус.")
        return redirect("event_detail", event_id=event.id)

    event.status = status
    event.save(update_fields=["status"])
    log_action(user=request.user, action="status", obj=event, details=f"Статус: {status}")
    messages.success(request, "Статус обновлён.")
    return redirect("event_detail", event_id=event.id)


# --------- Equipment inside Event (НЕ аренда) ---------

@login_required
def event_equipment_add_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventEquipmentForm(request.POST, event=event)
        if form.is_valid():
            equipment = form.cleaned_data.get("equipment")
            qty = int(form.cleaned_data.get("quantity") or 0)

            if not equipment or qty <= 0:
                messages.error(request, "Выбери оборудование и количество > 0.")
                return redirect("event_equipment_add", event_id=event.id)

            with transaction.atomic():
                item, created = EventEquipment.objects.select_for_update().get_or_create(
                    event=event,
                    equipment=equipment,
                    defaults={"quantity": qty},
                )
                if not created:
                    item.quantity = int(item.quantity or 0) + qty
                    item.save(update_fields=["quantity"])

            log_action(user=request.user, action="add", obj=event, details=f"Добавлено оборудование: {equipment} x{qty}")
            messages.success(request, "Оборудование добавлено.")
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventEquipmentForm(event=event)

    return render(request, "events/event_equipment_add.html", {"event": event, "form": form})


@login_required
def event_equipment_update_qty_view(request: HttpRequest, event_id: int, item_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method == "POST":
        qty = _safe_int(request.POST.get("quantity"), 0)
        if qty <= 0:
            item.delete()
            log_action(user=request.user, action="delete", obj=event, details=f"Удалено оборудование: {item.equipment}")
            messages.success(request, "Позиция удалена.")
        else:
            item.quantity = qty
            item.save(update_fields=["quantity"])
            log_action(user=request.user, action="update", obj=event, details=f"Изменено оборудование: {item.equipment} -> {qty}")
            messages.success(request, "Количество обновлено.")
    return redirect("event_detail", event_id=event.id)


@login_required
def event_equipment_delete_view(request: HttpRequest, event_id: int, item_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventEquipment, id=item_id, event=event)
    if request.method == "POST":
        eq = item.equipment
        item.delete()
        log_action(user=request.user, action="delete", obj=event, details=f"Удалено оборудование: {eq}")
        messages.success(request, "Удалено.")
    return redirect("event_detail", event_id=event.id)


# --------- Rented equipment inside Event ---------

@login_required
def event_rented_add_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventRentedEquipmentForm(request.POST, event=event)
        if form.is_valid():
            equipment = form.cleaned_data.get("equipment")
            qty = int(form.cleaned_data.get("quantity") or 0)

            if not equipment or qty <= 0:
                messages.error(request, "Выбери оборудование и количество > 0.")
                return redirect("event_rented_add", event_id=event.id)

            with transaction.atomic():
                item, created = EventRentedEquipment.objects.select_for_update().get_or_create(
                    event=event,
                    equipment=equipment,
                    defaults={"quantity": qty},
                )
                if not created:
                    item.quantity = int(item.quantity or 0) + qty
                    item.save(update_fields=["quantity"])

            log_action(user=request.user, action="add", obj=event, details=f"Добавлена аренда: {equipment} x{qty}")
            messages.success(request, "Аренда добавлена.")
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventRentedEquipmentForm(event=event)

    return render(request, "events/event_rented_add.html", {"event": event, "form": form})


@login_required
def event_rented_update_qty_view(request: HttpRequest, event_id: int, item_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method == "POST":
        qty = _safe_int(request.POST.get("quantity"), 0)
        if qty <= 0:
            item.delete()
            log_action(user=request.user, action="delete", obj=event, details=f"Удалена аренда: {item.equipment}")
            messages.success(request, "Позиция удалена.")
        else:
            item.quantity = qty
            item.save(update_fields=["quantity"])
            log_action(user=request.user, action="update", obj=event, details=f"Изменена аренда: {item.equipment} -> {qty}")
            messages.success(request, "Количество обновлено.")
    return redirect("event_detail", event_id=event.id)


@login_required
def event_rented_delete_view(request: HttpRequest, event_id: int, item_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)
    if request.method == "POST":
        eq = item.equipment
        item.delete()
        log_action(user=request.user, action="delete", obj=event, details=f"Удалена аренда: {eq}")
        messages.success(request, "Удалено.")
    return redirect("event_detail", event_id=event.id)
