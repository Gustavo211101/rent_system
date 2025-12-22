from __future__ import annotations

import calendar
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import (
    user_can_edit_event_card,
    user_can_edit_event_equipment,
)

from inventory.models import Equipment
from .forms import EventForm, EventEquipmentForm, EventRentedEquipmentForm
from .models import Event, EventEquipment, EventRentedEquipment


# =========================
# Helpers
# =========================

def _event_end(ev: Event) -> date:
    return ev.end_date or ev.start_date


def _overlap_q(prefix: str, start: date, end: date) -> Q:
    """
    Пересечение диапазонов дат (включительно) для DateField:
      start_date <= end AND end_date >= start
    end_date может быть NULL => считаем end_date = start_date
    """
    return (
        Q(**{f"{prefix}start_date__lte": end})
        & (
            Q(**{f"{prefix}end_date__gte": start})
            | (Q(**{f"{prefix}end_date__isnull": True}) & Q(**{f"{prefix}start_date__gte": start}))
        )
    )


def auto_close_past_events():
    today = date.today()

    Event.objects.filter(
        status__in=[Event.STATUS_DRAFT, Event.STATUS_CONFIRMED, Event.STATUS_CANCELLED],
        end_date__isnull=False,
        end_date__lt=today,
    ).update(status=Event.STATUS_CLOSED)

    Event.objects.filter(
        status__in=[Event.STATUS_DRAFT, Event.STATUS_CONFIRMED, Event.STATUS_CANCELLED],
        end_date__isnull=True,
        start_date__lt=today,
    ).update(status=Event.STATUS_CLOSED)


def _can_modify_card(user, event: Event) -> bool:
    if user.is_superuser:
        return True
    if event.status == Event.STATUS_CLOSED:
        return False
    return user_can_edit_event_card(user)


def _can_modify_equipment(user, event: Event) -> bool:
    if user.is_superuser:
        return True
    if event.status == Event.STATUS_CLOSED:
        return False
    return user_can_edit_event_equipment(user)


def _event_reserved_other_map(event: Event) -> dict:
    start = event.start_date
    end = _event_end(event)

    reserved = (
        EventEquipment.objects
        .filter(_overlap_q("event__", start, end))
        .exclude(event=event)
        .values("equipment_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["equipment_id"]: int(row["total"] or 0) for row in reserved}


def _event_required_map(event: Event) -> dict:
    required = (
        EventEquipment.objects
        .filter(event=event)
        .values("equipment_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["equipment_id"]: int(row["total"] or 0) for row in required}


def _event_rented_map(event: Event) -> dict:
    rented = (
        EventRentedEquipment.objects
        .filter(event=event)
        .values("equipment_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["equipment_id"]: int(row["total"] or 0) for row in rented}


def _event_shortages(event: Event) -> list[dict]:
    reserved_other = _event_reserved_other_map(event)
    required_map = _event_required_map(event)
    rented_map = _event_rented_map(event)

    if not required_map:
        return []

    equipment_objs = Equipment.objects.filter(id__in=required_map.keys())
    result = []

    for eq in equipment_objs:
        required = int(required_map.get(eq.id, 0))
        rented = int(rented_map.get(eq.id, 0))
        used_other = int(reserved_other.get(eq.id, 0))

        available_own = int(eq.quantity_total) - used_other
        if available_own < 0:
            available_own = 0

        effective = available_own + rented
        shortage = required - effective
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


def _event_has_shortage(event: Event) -> bool:
    return len(_event_shortages(event)) > 0


# =========================
# Views
# =========================

@login_required
def calendar_view(request):
    auto_close_past_events()

    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(year, month)

    grid_start = month_days[0][0]
    grid_end = month_days[-1][-1]

    events = Event.objects.filter(_overlap_q("", grid_start, grid_end)).order_by("start_date", "id")

    events_by_day: dict[date, list[Event]] = {}
    event_has_problem: dict[int, bool] = {}

    for ev in events:
        event_has_problem[ev.id] = _event_has_shortage(ev)

        d = ev.start_date
        ev_end = _event_end(ev)
        while d <= ev_end:
            events_by_day.setdefault(d, []).append(ev)
            d += timedelta(days=1)

    for d in list(events_by_day.keys()):
        events_by_day[d].sort(key=lambda x: (x.start_date, x.name.lower()))

    return render(request, "events/calendar.html", {
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "month_days": month_days,
        "events_by_day": events_by_day,
        "event_has_problem": event_has_problem,   # ВАЖНО: чтобы шаблон не падал
        "can_edit": user_can_edit_event_card(request.user),
    })


@login_required
def event_list_view(request):
    auto_close_past_events()
    events = Event.objects.order_by("-start_date", "-id")
    return render(request, "events/event_list.html", {
        "events": events,
        "can_edit": user_can_edit_event_card(request.user),
    })


@login_required
def event_detail_view(request, event_id):
    auto_close_past_events()

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

    shortages = _event_shortages(event)

    return render(request, "events/event_detail.html", {
        "event": event,
        "event_end": _event_end(event),
        "equipment_items": equipment_items,
        "rented_items": rented_items,
        "shortages": shortages,
        "has_shortage": len(shortages) > 0,
        "can_edit": user_can_edit_event_card(request.user),
        "can_modify_card": _can_modify_card(request.user, event),
        "can_modify_equipment": _can_modify_equipment(request.user, event),
    })


@login_required
def event_create_view(request):
    if not user_can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            if not event.end_date:
                event.end_date = event.start_date
            if not event.responsible:
                event.responsible = request.user
            event.save()
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventForm()

    return render(request, "events/event_form.html", {"form": form, "title": "Создание мероприятия"})


@login_required
def event_update_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_card(request.user, event):
        return HttpResponseForbidden("Нельзя редактировать это мероприятие")

    if request.method == "POST":
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            ev = form.save(commit=False)
            if not ev.end_date:
                ev.end_date = ev.start_date
            ev.save()
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventForm(instance=event)

    return render(request, "events/event_form.html", {"form": form, "title": "Редактирование мероприятия"})


@login_required
def event_set_status_view(request, event_id, status):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_card(request.user, event):
        return HttpResponseForbidden("Нельзя менять статус")

    allowed = {s[0] for s in Event.STATUS_CHOICES}
    if status not in allowed:
        return redirect("event_detail", event_id=event.id)

    event.status = status
    event.save(update_fields=["status"])
    return redirect("event_detail", event_id=event.id)


# =========================
# Equipment on event
# =========================

@login_required
def event_equipment_add_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_equipment(request.user, event):
        return HttpResponseForbidden("Недостаточно прав на оборудование")

    if request.method == "POST":
        form = EventEquipmentForm(request.POST, event=event)
        if form.is_valid():
            eq = form.cleaned_data["equipment"]
            qty = int(form.cleaned_data.get("quantity") or 0)

            if qty <= 0:
                return redirect("event_detail", event_id=event.id)

            existing = EventEquipment.objects.filter(event=event, equipment=eq).first()
            if existing:
                existing.quantity = int(existing.quantity) + qty
                existing.save()
            else:
                EventEquipment.objects.create(event=event, equipment=eq, quantity=qty)

            return redirect("event_detail", event_id=event.id)
    else:
        form = EventEquipmentForm(event=event)

    equipment_items = (
        EventEquipment.objects
        .filter(event=event)
        .select_related("equipment")
        .order_by("equipment__name")
    )

    return render(request, "events/event_equipment_add.html", {
        "event": event,
        "form": form,
        "equipment_items": equipment_items,
        "shortages": _event_shortages(event),
    })


@login_required
def event_equipment_update_qty_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_equipment(request.user, event):
        return HttpResponseForbidden("Недостаточно прав на оборудование")

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method != "POST":
        return redirect("event_detail", event_id=event.id)

    qty_raw = (request.POST.get("quantity") or "").strip()
    try:
        qty = int(qty_raw)
    except ValueError:
        return redirect("event_detail", event_id=event.id)

    if qty <= 0:
        item.delete()
        return redirect("event_detail", event_id=event.id)

    item.quantity = qty
    item.save()
    return redirect("event_detail", event_id=event.id)


@login_required
def event_equipment_delete_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_equipment(request.user, event):
        return HttpResponseForbidden("Недостаточно прав на оборудование")

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method == "POST":
        item.delete()

    return redirect("event_detail", event_id=event.id)


@login_required
def event_mark_equipment_tbd_view(request, event_id):
    # Ты просил убрать "оборудование позже" — оставляем view только для совместимости URL
    return redirect("event_detail", event_id=event_id)


# =========================
# Rented equipment (covers shortage)
# =========================

@login_required
def event_rented_add_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_equipment(request.user, event):
        return HttpResponseForbidden("Недостаточно прав на аренду")

    if request.method == "POST":
        form = EventRentedEquipmentForm(request.POST, event=event)
        if form.is_valid():
            eq = form.cleaned_data["equipment"]
            qty = int(form.cleaned_data.get("quantity") or 0)

            if qty <= 0:
                return redirect("event_detail", event_id=event.id)

            existing = EventRentedEquipment.objects.filter(event=event, equipment=eq).first()
            if existing:
                existing.quantity = int(existing.quantity) + qty
                existing.save()
            else:
                EventRentedEquipment.objects.create(event=event, equipment=eq, quantity=qty)

            return redirect("event_detail", event_id=event.id)
    else:
        form = EventRentedEquipmentForm(event=event)

    rented_items = (
        EventRentedEquipment.objects
        .filter(event=event)
        .select_related("equipment")
        .order_by("equipment__name")
    )

    return render(request, "events/event_rented_add.html", {
        "event": event,
        "form": form,
        "rented_items": rented_items,
        "shortages": _event_shortages(event),
    })


@login_required
def event_rented_update_qty_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_equipment(request.user, event):
        return HttpResponseForbidden("Недостаточно прав на аренду")

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method != "POST":
        return redirect("event_detail", event_id=event.id)

    qty_raw = (request.POST.get("quantity") or "").strip()
    try:
        qty = int(qty_raw)
    except ValueError:
        return redirect("event_detail", event_id=event.id)

    if qty <= 0:
        item.delete()
        return redirect("event_detail", event_id=event.id)

    item.quantity = qty
    item.save()
    return redirect("event_detail", event_id=event.id)


@login_required
def event_rented_delete_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_equipment(request.user, event):
        return HttpResponseForbidden("Недостаточно прав на аренду")

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method == "POST":
        item.delete()

    return redirect("event_detail", event_id=event.id)