from __future__ import annotations

import calendar as pycalendar
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponseForbidden, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import (
    can_edit_event_card,
    can_edit_event_equipment,
)

# Если у тебя подключено логирование (audit app) — используем.
# Если нет — просто не упадём.
try:
    from audit.utils import log_action  # type: ignore
except Exception:  # pragma: no cover
    def log_action(*args, **kwargs):  # type: ignore
        return None


from .models import Event, EventEquipment, EventRentedEquipment  # поправь импорт, если у тебя иначе
from .forms import EventForm, EventEquipmentForm, EventRentedEquipmentForm  # поправь импорт, если у тебя иначе


# ---------- helpers ----------

def _safe_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last_day = pycalendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    return first, last


def _calculate_shortages(event: Event):
    """
    Возвращает список строк:
    {
      equipment: Equipment,
      required: int,
      available_own: int,
      rented: int,
      shortage: int
    }
    Если какие-то поля/методы отличаются — не падаем, а возвращаем [].
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
            # У тебя в inventory.models.Equipment есть available_quantity(start,end)
            available_own = int(eq.available_quantity(start, end))  # type: ignore
        except Exception:
            # если метода нет — попробуем по quantity_total хотя бы
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


def _parse_year_month(request: HttpRequest) -> tuple[int, int]:
    """
    Берём year/month из query (?year=2025&month=12), иначе текущие.
    """
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


# ---------- views ----------

@login_required
def calendar_view(request: HttpRequest) -> HttpResponse:
    year, month = _parse_year_month(request)
    month_start, month_end = _month_bounds(year, month)

    # Вытаскиваем события, которые пересекают месяц:
    # start_date <= month_end AND end_date >= month_start
    events_qs = (
        Event.objects
        .filter(start_date__lte=month_end, end_date__gte=month_start)
        .select_related("responsible")  # responsible у тебя FK, client — НЕ FK, поэтому НЕ трогаем
        .order_by("start_date")
    )

    # Разложим по дням месяца (ключ = date)
    events_by_day: dict[date, list[Event]] = {}
    for e in events_qs:
        try:
            cur = max(e.start_date, month_start)
            end = min(e.end_date, month_end)
            while cur <= end:
                events_by_day.setdefault(cur, []).append(e)
                cur = cur + timedelta(days=1)  # <- важно, без replace(day=day+1)
        except Exception:
            continue

    cal = pycalendar.Calendar(firstweekday=0)
    month_days = list(cal.monthdatescalendar(year, month))

    # Флаги проблем по мероприятиям (нехватка)
    event_has_problem: dict[int, bool] = {}
    try:
        for e in events_qs:
            shortages = _calculate_shortages(e)
            event_has_problem[e.id] = bool(shortages)
    except Exception:
        event_has_problem = {}

    ctx = {
        "year": year,
        "month": month,
        "month_name": pycalendar.month_name[month],
        "month_days": month_days,
        "events_by_day": events_by_day,
        "event_has_problem": event_has_problem,
    }
    return render(request, "events/calendar.html", ctx)


@login_required
def event_list_view(request):
    events = Event.objects.all().order_by("-start_date")

    return render(request, "events/event_list.html", {
        "events": events,
        "can_create_event": can_edit_event_card(request.user),
    })


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
        "can_modify": can_edit_event_card(request.user),              # для кнопок статуса/редактирования
        "can_edit_equipment": can_edit_event_equipment(request.user), # для оборудования/аренды
    }
    # ВАЖНО: твой шаблон event_detail.html сейчас проверяет can_modify.
    # Если ты хочешь: карточка только менеджер, а оборудование может старший инженер —
    # то в шаблоне надо использовать can_edit_equipment для таблиц оборудования/аренды.
    return render(request, "events/event_detail.html", ctx)


@login_required
def event_create_view(request: HttpRequest) -> HttpResponse:
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save()
            log_action(user=request.user, action="create", obj=event, details="Создано мероприятие")
            messages.success(request, "Мероприятие создано.")
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventForm()

    return render(request, "events/event_form.html", {"form": form, "title": "Создать мероприятие"})


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

    allowed = {c[0] for c in getattr(Event, "STATUS_CHOICES", [])} or {"draft", "confirmed", "cancelled", "closed"}
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
            # Ключевой момент: EventEquipmentForm у тебя, судя по ошибкам, требует event,
            # а также может НЕ ставить event автоматически. Поэтому ставим вручную.
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
