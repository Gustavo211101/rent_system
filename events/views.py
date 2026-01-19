from __future__ import annotations

import calendar as pycalendar
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import can_edit_event_card, can_edit_event_equipment

try:
    from audit.utils import log_action  # type: ignore
except Exception:  # pragma: no cover
    def log_action(*args, **kwargs):  # type: ignore
        return None

from .forms import EventEquipmentForm, EventForm, EventRentedEquipmentForm
from .models import Event, EventEquipment, EventRentedEquipment
from .utils import auto_close_past_events, calculate_shortages


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
    return year, month


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last_day = pycalendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    return first, last


@login_required
def calendar_view(request: HttpRequest) -> HttpResponse:
    auto_close_past_events()

    year, month = _parse_year_month(request)
    month_start, month_end = _month_bounds(year, month)

    cal_filter = (request.GET.get("filter") or "all").strip()
    if cal_filter not in {"all", "confirmed", "mine"}:
        cal_filter = "all"

    qs = (
        Event.objects
        .filter(start_date__lte=month_end, end_date__gte=month_start)
        .select_related("responsible", "s_engineer")
        .prefetch_related("engineers")
        .order_by("start_date", "id")
    )

    if cal_filter == "confirmed":
        qs = qs.filter(status="confirmed")
    elif cal_filter == "mine":
        qs = qs.filter(
            Q(responsible=request.user)
            | Q(s_engineer=request.user)
            | Q(engineers=request.user)
        ).distinct()

    event_problem: dict[int, bool] = {}
    for e in qs:
        event_problem[e.id] = bool(calculate_shortages(e))

    events_by_day: dict[date, list[dict]] = defaultdict(list)

    for e in qs:
        start = max(e.start_date, month_start)
        end = min(e.end_date, month_end)

        d = start
        while d <= end:
            is_start = (d == e.start_date)
            is_end = (d == e.end_date)
            is_single = (e.start_date == e.end_date)

            if e.start_date < month_start and d == month_start:
                is_start = True
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

    for k in events_by_day:
        events_by_day[k].sort(key=lambda x: (x["event"].start_date, x["event"].id))

    month_days = list(pycalendar.Calendar(firstweekday=0).monthdatescalendar(year, month))

    ctx = {
        "year": year,
        "month": month,
        "month_name": pycalendar.month_name[month],
        "month_days": month_days,
        "events_by_day": dict(events_by_day),

        "filter": cal_filter,
        "can_create_event": can_edit_event_card(request.user),
    }
    return render(request, "events/calendar.html", ctx)


@login_required
def event_list_view(request: HttpRequest) -> HttpResponse:
    qs = (
        Event.objects
        .all()
        .select_related("responsible", "s_engineer")
        .prefetch_related("engineers")
        .order_by("-start_date", "-id")
    )
    return render(request, "events/event_list.html", {
        "events": qs,
        "can_create_event": can_edit_event_card(request.user),
    })


@login_required
def event_detail_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(
        Event.objects.select_related("responsible", "s_engineer").prefetch_related("engineers"),
        id=event_id,
    )

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

    shortages = calculate_shortages(event)

    return render(request, "events/event_detail.html", {
        "event": event,
        "equipment_items": equipment_items,
        "rented_items": rented_items,
        "shortages": shortages,
        "can_modify": can_edit_event_card(request.user),
        "can_edit_equipment": can_edit_event_equipment(request.user),
    })


@login_required
def event_create_view(request: HttpRequest) -> HttpResponse:
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    initial = {}
    sd = (request.GET.get("start_date") or "").strip()
    ed = (request.GET.get("end_date") or "").strip()
    nm = (request.GET.get("name") or "").strip()

    if sd:
        initial["start_date"] = sd
        initial["end_date"] = ed or sd
    if nm:
        initial["name"] = nm

    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save()
            log_action(user=request.user, action="create", obj=event, details="Создано мероприятие")
            messages.success(request, "Мероприятие создано.")
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventForm(initial=initial)

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

    allowed = {"draft", "confirmed", "cancelled", "closed"}
    if status not in allowed:
        messages.error(request, "Некорректный статус.")
        return redirect("event_detail", event_id=event.id)

    event.status = status
    event.save(update_fields=["status"])
    log_action(user=request.user, action="status", obj=event, details=f"Статус: {status}")
    messages.success(request, "Статус обновлён.")
    return redirect("event_detail", event_id=event.id)


@login_required
def event_equipment_add_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventEquipmentForm(request.POST, event=event)
        if form.is_valid():
            equipment = form.cleaned_data["equipment"]
            qty = int(form.cleaned_data.get("quantity") or 0)
            if qty <= 0:
                return redirect("event_detail", event_id=event.id)

            item, created = EventEquipment.objects.get_or_create(
                event=event,
                equipment=equipment,
                defaults={"quantity": 0},
            )
            if not created:
                item.quantity = int(item.quantity or 0) + qty
                item.save(update_fields=["quantity"])
            else:
                item.quantity = qty
                item.save(update_fields=["quantity"])

            log_action(user=request.user, action="update", obj=event, details=f"Добавлено оборудование: {equipment.name} +{qty}")
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
        else:
            item.quantity = qty
            item.save(update_fields=["quantity"])

    return redirect("event_detail", event_id=event.id)


@login_required
def event_equipment_delete_view(request: HttpRequest, event_id: int, item_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventEquipment, id=item_id, event=event)
    if request.method == "POST":
        item.delete()
    return redirect("event_detail", event_id=event.id)


@login_required
def event_rented_add_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    shortages = calculate_shortages(event)

    if request.method == "POST":
        form = EventRentedEquipmentForm(request.POST, event=event)
        if form.is_valid():
            equipment = form.cleaned_data["equipment"]
            qty = int(form.cleaned_data.get("quantity") or 0)
            if qty <= 0:
                return redirect("event_detail", event_id=event.id)

            item, created = EventRentedEquipment.objects.get_or_create(
                event=event,
                equipment=equipment,
                defaults={"quantity": 0},
            )
            if not created:
                item.quantity = int(item.quantity or 0) + qty
                item.save(update_fields=["quantity"])
            else:
                item.quantity = qty
                item.save(update_fields=["quantity"])

            messages.success(request, "Аренда добавлена.")
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventRentedEquipmentForm(event=event)

    return render(request, "events/event_rented_add.html", {
        "event": event,
        "form": form,
        "shortages": shortages,
        "has_shortage": bool(shortages),
    })


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
        else:
            item.quantity = qty
            item.save(update_fields=["quantity"])

    return redirect("event_detail", event_id=event.id)


@login_required
def event_rented_delete_view(request: HttpRequest, event_id: int, item_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)
    if request.method == "POST":
        item.delete()
    return redirect("event_detail", event_id=event.id)


# ---------------------------
# API: quick-create (modal)
# ---------------------------

@login_required
def quick_create_event_api(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    if not can_edit_event_card(request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    try:
        import json
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Bad JSON"}, status=400)

    name = (payload.get("name") or "").strip()
    start = (payload.get("start_date") or "").strip()
    end = (payload.get("end_date") or "").strip()

    if not name:
        return JsonResponse({"ok": False, "error": "Название обязательно"}, status=400)
    if not start:
        return JsonResponse({"ok": False, "error": "Дата начала обязательна"}, status=400)

    try:
        sd = datetime.strptime(start, "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({"ok": False, "error": "Неверный формат start_date"}, status=400)

    if end:
        try:
            ed = datetime.strptime(end, "%Y-%m-%d").date()
        except Exception:
            return JsonResponse({"ok": False, "error": "Неверный формат end_date"}, status=400)
    else:
        ed = sd

    if ed < sd:
        return JsonResponse({"ok": False, "error": "Дата окончания раньше даты начала"}, status=400)

    event = Event.objects.create(
        name=name,
        start_date=sd,
        end_date=ed,
        responsible=request.user,
        status="draft",
    )
    log_action(user=request.user, action="create", obj=event, details="Создано из календаря (модалка)")
    return JsonResponse({"ok": True, "id": event.id})


@login_required
def quick_move_event_api(request: HttpRequest, event_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    if not can_edit_event_card(request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    event = get_object_or_404(Event, id=event_id)

    try:
        import json
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Bad JSON"}, status=400)

    new_start = (payload.get("new_start_date") or "").strip()
    if not new_start:
        return JsonResponse({"ok": False, "error": "new_start_date required"}, status=400)

    try:
        ns = datetime.strptime(new_start, "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({"ok": False, "error": "Bad date format"}, status=400)

    duration = (event.end_date - event.start_date).days
    event.start_date = ns
    event.end_date = ns + timedelta(days=duration)
    event.save(update_fields=["start_date", "end_date"])
    log_action(user=request.user, action="update", obj=event, details=f"Перенос (drag&drop) на {ns}")
    return JsonResponse({"ok": True})
