from datetime import date, timedelta
import calendar

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from accounts.permissions import user_can_edit
from audit.utils import log_action
from inventory.models import Equipment
from .models import Event, EventEquipment, EventRentedEquipment
from .forms import EventForm, EventEquipmentForm, EventRentedEquipmentForm


# =========================
# Helpers
# =========================

def _event_end(event: Event) -> date:
    return event.end_date or event.start_date


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


def _can_modify_event(user, event: Event) -> bool:
    if user.is_superuser:
        return True
    if event.status == Event.STATUS_CLOSED:
        return False
    return user_can_edit(user)


def _overlap_q(prefix: str, start: date, end: date) -> Q:
    return (
        Q(**{f"{prefix}start_date__lte": end})
        & (
            Q(**{f"{prefix}end_date__gte": start})
            | (Q(**{f"{prefix}end_date__isnull": True}) & Q(**{f"{prefix}start_date__gte": start}))
        )
    )


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


def _event_shortages(event: Event) -> list:
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

    events = Event.objects.filter(_overlap_q("", grid_start, grid_end))

    events_by_day = {}
    for ev in events:
        ev_end = _event_end(ev)
        d = ev.start_date
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
        "can_edit": user_can_edit(request.user),
    })


@login_required
def event_list_view(request):
    auto_close_past_events()
    events = Event.objects.order_by("-start_date", "-id")
    return render(request, "events/event_list.html", {
        "events": events,
        "can_edit": user_can_edit(request.user),
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
    can_modify = _can_modify_event(request.user, event)

    return render(request, "events/event_detail.html", {
        "event": event,
        "event_end": _event_end(event),
        "equipment_items": equipment_items,
        "rented_items": rented_items,
        "shortages": shortages,
        "has_shortage": len(shortages) > 0,
        "can_edit": user_can_edit(request.user),
        "can_modify": can_modify,
    })


@login_required
def event_create_view(request):
    if not user_can_edit(request.user):
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
            log_action(user=request.user, action="create", obj=event, details="Создано мероприятие")
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventForm()

    return render(request, "events/event_form.html", {
        "form": form,
        "title": "Создание мероприятия",
    })


@login_required
def event_update_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden("Нельзя редактировать это мероприятие")

    if request.method == "POST":
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            ev = form.save(commit=False)
            if not ev.end_date:
                ev.end_date = ev.start_date
            ev.save()
            log_action(user=request.user, action="update", obj=ev, details="Изменена карточка мероприятия")
            return redirect("event_detail", event_id=ev.id)
    else:
        form = EventForm(instance=event)

    return render(request, "events/event_form.html", {
        "form": form,
        "title": "Редактирование мероприятия",
    })


@login_required
def event_set_status_view(request, event_id, status):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden("Нельзя менять статус этого мероприятия")

    allowed_statuses = {s[0] for s in Event.STATUS_CHOICES}
    if status not in allowed_statuses:
        return redirect("event_detail", event_id=event.id)

    old = event.status
    event.status = status
    event.save(update_fields=["status"])
    log_action(
        user=request.user,
        action="update",
        obj=event,
        details=f"Смена статуса: {old} -> {status}",
    )
    return redirect("event_detail", event_id=event.id)


# =========================
# Equipment on event
# =========================

@login_required
def event_equipment_add_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden("Нельзя изменять оборудование у закрытого мероприятия")

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
                log_action(
                    user=request.user,
                    action="update",
                    obj=event,
                    details=f"Оборудование: +{qty} к {eq.name} (итого {existing.quantity})",
                )
            else:
                EventEquipment.objects.create(event=event, equipment=eq, quantity=qty)
                log_action(
                    user=request.user,
                    action="create",
                    obj=event,
                    details=f"Оборудование: добавлено {eq.name} x{qty}",
                )

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
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden("Нельзя изменять оборудование у закрытого мероприятия")

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method != "POST":
        return redirect("event_detail", event_id=event.id)

    try:
        qty = int((request.POST.get("quantity") or "0").strip())
    except ValueError:
        return redirect("event_detail", event_id=event.id)

    if qty <= 0:
        eq_name = item.equipment.name
        item.delete()
        log_action(user=request.user, action="delete", obj=event, details=f"Оборудование: удалено {eq_name}")
        return redirect("event_detail", event_id=event.id)

    old = item.quantity
    item.quantity = qty
    item.save()
    log_action(user=request.user, action="update", obj=event, details=f"Оборудование: {item.equipment.name} {old} -> {qty}")
    return redirect("event_detail", event_id=event.id)


@login_required
def event_equipment_delete_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden("Нельзя изменять оборудование у закрытого мероприятия")

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method == "POST":
        eq_name = item.equipment.name
        item.delete()
        log_action(user=request.user, action="delete", obj=event, details=f"Оборудование: удалено {eq_name}")

    return redirect("event_detail", event_id=event.id)


@login_required
def event_mark_equipment_tbd_view(request, event_id):
    return redirect("event_detail", event_id=event_id)


# =========================
# Rented on event
# =========================

@login_required
def event_rented_add_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden("Нельзя изменять аренду у закрытого мероприятия")

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
                log_action(
                    user=request.user,
                    action="update",
                    obj=event,
                    details=f"Аренда: +{qty} к {eq.name} (итого {existing.quantity})",
                )
            else:
                EventRentedEquipment.objects.create(event=event, equipment=eq, quantity=qty)
                log_action(user=request.user, action="create", obj=event, details=f"Аренда: добавлено {eq.name} x{qty}")

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
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden("Нельзя изменять аренду у закрытого мероприятия")

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method != "POST":
        return redirect("event_detail", event_id=event.id)

    try:
        qty = int((request.POST.get("quantity") or "0").strip())
    except ValueError:
        return redirect("event_detail", event_id=event.id)

    if qty <= 0:
        eq_name = item.equipment.name
        item.delete()
        log_action(user=request.user, action="delete", obj=event, details=f"Аренда: удалено {eq_name}")
        return redirect("event_detail", event_id=event.id)

    old = item.quantity
    item.quantity = qty
    item.save()
    log_action(user=request.user, action="update", obj=event, details=f"Аренда: {item.equipment.name} {old} -> {qty}")
    return redirect("event_detail", event_id=event.id)


@login_required
def event_rented_delete_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden("Нельзя изменять аренду у закрытого мероприятия")

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method == "POST":
        eq_name = item.equipment.name
        item.delete()
        log_action(user=request.user, action="delete", obj=event, details=f"Аренда: удалено {eq_name}")

    return redirect("event_detail", event_id=event.id)
