from datetime import date
import calendar

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import (
    user_can_edit_event_card,
    user_can_edit_event_equipment,
)

from inventory.models import Equipment
from .models import Event, EventEquipment, EventRentedEquipment
from .forms import EventForm, EventEquipmentForm, EventRentedEquipmentForm


def auto_close_past_events():
    """
    На следующий день после окончания (end_date < сегодня) считаем мероприятие закрытым.
    """
    today = date.today()
    allowed = {s[0] for s in getattr(Event, "STATUS_CHOICES", [])}
    if "closed" not in allowed:
        return

    Event.objects.filter(end_date__lt=today).exclude(status="closed").update(status="closed")


def _event_overlaps_qs(start_d: date, end_d: date):
    # пересечение диапазонов по датам (включительно)
    # other.start <= end AND other.end >= start
    return Event.objects.filter(start_date__lte=end_d, end_date__gte=start_d)


def _reserved_other_map(event: Event) -> dict:
    qs = (
        EventEquipment.objects
        .filter(event__start_date__lte=event.end_date, event__end_date__gte=event.start_date)
        .exclude(event=event)
        .values("equipment_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["equipment_id"]: int(row["total"] or 0) for row in qs}


def _required_map(event: Event) -> dict:
    qs = (
        EventEquipment.objects
        .filter(event=event)
        .values("equipment_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["equipment_id"]: int(row["total"] or 0) for row in qs}


def _rented_map(event: Event) -> dict:
    qs = (
        EventRentedEquipment.objects
        .filter(event=event)
        .values("equipment_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["equipment_id"]: int(row["total"] or 0) for row in qs}


def event_shortages(event: Event) -> list:
    """
    Возвращает список нехваток оборудования по мероприятию.
    shortage считается с учетом арендованного (EventRentedEquipment).
    """
    required = _required_map(event)
    if not required:
        return []

    reserved_other = _reserved_other_map(event)
    rented = _rented_map(event)

    equipment_qs = Equipment.objects.filter(id__in=required.keys())
    result = []

    for eq in equipment_qs:
        need = required.get(eq.id, 0)
        other = reserved_other.get(eq.id, 0)
        rent = rented.get(eq.id, 0)

        own_available = eq.quantity_total - other
        if own_available < 0:
            own_available = 0

        effective = own_available + rent
        shortage = need - effective
        if shortage > 0:
            result.append({
                "equipment": eq,
                "required": need,
                "available_own": own_available,
                "rented": rent,
                "shortage": shortage,
            })

    result.sort(key=lambda x: x["shortage"], reverse=True)
    return result


@login_required
def calendar_view(request):
    auto_close_past_events()

    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(year, month)

    # границы месяца (для выборки событий, пересекающих месяц)
    first_day = month_days[0][0]
    last_day = month_days[-1][-1]

    events = Event.objects.filter(start_date__lte=last_day, end_date__gte=first_day).order_by("start_date")

    events_by_day = {d: [] for week in month_days for d in week}
    event_has_problem = {}

    for ev in events:
        # отмечаем проблему (нехватка) — для обводки в календаре
        event_has_problem[ev.id] = bool(event_shortages(ev))

        # раскладываем событие по дням, если оно многодневное
        cur = max(ev.start_date, first_day)
        end = min(ev.end_date, last_day)
        while cur <= end:
            if cur in events_by_day:
                events_by_day[cur].append(ev)
            cur = cur.fromordinal(cur.toordinal() + 1)

    return render(request, "events/calendar.html", {
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "month_days": month_days,
        "events_by_day": events_by_day,
        "event_has_problem": event_has_problem,  # важно: всегда dict, иначе календарь падает
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
def event_detail_view(request, event_id: int):
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

    shortages = event_shortages(event)

    return render(request, "events/event_detail.html", {
        "event": event,
        "equipment_items": equipment_items,
        "rented_items": rented_items,
        "shortages": shortages,

        # карточку может менять только менеджер
        "can_edit_card": user_can_edit_event_card(request.user),

        # оборудование может менять менеджер и старший инженер
        "can_edit_equipment": user_can_edit_event_equipment(request.user),
    })


@login_required
def event_create_view(request):
    if not user_can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            ev = form.save(commit=False)

            # ответственный (если есть поле responsible)
            if hasattr(ev, "responsible_id") and not ev.responsible_id:
                ev.responsible = request.user

            # если end_date пустой — делаем однодневным
            if not getattr(ev, "end_date", None) and getattr(ev, "start_date", None):
                ev.end_date = ev.start_date

            ev.save()
            return redirect("event_detail", ev.id)
    else:
        form = EventForm()

    return render(request, "events/event_form.html", {
        "form": form,
        "title": "Создать мероприятие",
    })


@login_required
def event_update_view(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)

    if not user_can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            ev = form.save(commit=False)

            if not getattr(ev, "end_date", None) and getattr(ev, "start_date", None):
                ev.end_date = ev.start_date

            ev.save()
            return redirect("event_detail", event.id)
    else:
        form = EventForm(instance=event)

    return render(request, "events/event_form.html", {
        "form": form,
        "title": "Редактировать мероприятие",
    })


@login_required
def event_set_status_view(request, event_id: int, status: str):
    event = get_object_or_404(Event, id=event_id)

    if not user_can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    allowed = {s[0] for s in getattr(Event, "STATUS_CHOICES", [])}
    if status not in allowed:
        return redirect("event_detail", event.id)

    event.status = status
    event.save(update_fields=["status"])
    return redirect("event_detail", event.id)


@login_required
def event_equipment_add_view(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)

    if not user_can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventEquipmentForm(request.POST, event=event)
        if form.is_valid():
            eq = form.cleaned_data["equipment"]
            qty = int(form.cleaned_data.get("quantity") or 0)

            if qty <= 0:
                return redirect("event_detail", event.id)

            item, created = EventEquipment.objects.get_or_create(
                event=event,
                equipment=eq,
                defaults={"quantity": qty},
            )
            if not created:
                item.quantity = int(item.quantity or 0) + qty
                item.save(update_fields=["quantity"])

            return redirect("event_detail", event.id)
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
        "shortages": event_shortages(event),
    })


@login_required
def event_equipment_update_qty_view(request, event_id: int, item_id: int):
    event = get_object_or_404(Event, id=event_id)

    if not user_can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method != "POST":
        return redirect("event_detail", event.id)

    raw = (request.POST.get("quantity") or "").strip()
    try:
        qty = int(raw)
    except ValueError:
        return redirect("event_detail", event.id)

    if qty <= 0:
        item.delete()
        return redirect("event_detail", event.id)

    item.quantity = qty
    item.save(update_fields=["quantity"])
    return redirect("event_detail", event.id)


@login_required
def event_equipment_delete_view(request, event_id: int, item_id: int):
    event = get_object_or_404(Event, id=event_id)

    if not user_can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method == "POST":
        item.delete()

    return redirect("event_detail", event.id)


@login_required
def event_rented_add_view(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)

    if not user_can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventRentedEquipmentForm(request.POST, event=event)
        if form.is_valid():
            eq = form.cleaned_data["equipment"]
            qty = int(form.cleaned_data.get("quantity") or 0)

            if qty <= 0:
                return redirect("event_detail", event.id)

            item, created = EventRentedEquipment.objects.get_or_create(
                event=event,
                equipment=eq,
                defaults={"quantity": qty},
            )
            if not created:
                item.quantity = int(item.quantity or 0) + qty
                item.save(update_fields=["quantity"])

            return redirect("event_detail", event.id)
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
        "shortages": event_shortages(event),
    })


@login_required
def event_rented_update_qty_view(request, event_id: int, item_id: int):
    event = get_object_or_404(Event, id=event_id)

    if not user_can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method != "POST":
        return redirect("event_detail", event.id)

    raw = (request.POST.get("quantity") or "").strip()
    try:
        qty = int(raw)
    except ValueError:
        return redirect("event_detail", event.id)

    if qty <= 0:
        item.delete()
        return redirect("event_detail", event.id)

    item.quantity = qty
    item.save(update_fields=["quantity"])
    return redirect("event_detail", event.id)


@login_required
def event_rented_delete_view(request, event_id: int, item_id: int):
    event = get_object_or_404(Event, id=event_id)

    if not user_can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method == "POST":
        item.delete()

    return redirect("event_detail", event.id)
