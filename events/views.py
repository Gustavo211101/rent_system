from __future__ import annotations

import calendar as pycalendar
from datetime import datetime, timedelta
from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import can_edit_event_card, can_edit_event_equipment
from accounts.roles import ROLE_MANAGER, ROLE_SENIOR_ENGINEER

try:
    from audit.utils import log_action  # type: ignore
except Exception:  # pragma: no cover
    def log_action(*args, **kwargs):  # type: ignore
        return None

from .forms import EventEquipmentForm, EventForm, EventRentedEquipmentForm, EventStockReservationForm
from .models import Event, EventEquipment, EventRentedEquipment, EventStockReservation
from .utils import auto_close_past_events, calculate_shortages

from inventory.models import StockEquipmentType


# =========================
# helpers
# =========================

def _safe_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _parse_year_month(request: HttpRequest) -> tuple[int, int]:
    today = timezone.localdate()
    year = _safe_int(request.GET.get("year"), today.year)
    month = _safe_int(request.GET.get("month"), today.month)
    month = max(1, min(12, month))
    return year, month


def _pack_lanes(segments: list[dict]) -> list[dict]:
    lanes: list[list[tuple[int, int]]] = []
    for seg in sorted(segments, key=lambda s: (s["start_col"], s["end_col"], s["event"].id)):
        placed = False
        for lane_idx, used in enumerate(lanes):
            conflict = any(not (seg["end_col"] < a or seg["start_col"] > b) for a, b in used)
            if not conflict:
                seg["lane"] = lane_idx
                used.append((seg["start_col"], seg["end_col"]))
                placed = True
                break
        if not placed:
            seg["lane"] = len(lanes)
            lanes.append([(seg["start_col"], seg["end_col"])])
    return segments


def _can_view_all_events(user) -> bool:
    """
    Видеть ВСЕ мероприятия могут:
    - superuser
    - пользователи в группе ROLE_MANAGER
    - пользователи в группе ROLE_SENIOR_ENGINEER
    Остальные — только мероприятия, где они участвуют.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    groups = set(user.groups.values_list("name", flat=True))
    return (ROLE_MANAGER in groups) or (ROLE_SENIOR_ENGINEER in groups)


def _stock_available_for_event(event: Event, equipment_type: StockEquipmentType, exclude_event_id: int | None = None) -> int:
    """Доступное количество данного типа на даты события (фаза 1)."""
    sd = event.start_date
    ed = event.end_date or event.start_date
    return EventStockReservation.available_for_dates(
        equipment_type=equipment_type,
        start_date=sd,
        end_date=ed,
        exclude_event_id=exclude_event_id,
    )


def _participation_q(user) -> Q:
    """
    Участие в мероприятии:
    - ответственный / старший инженер / инженеры
    - + пользователи в дополнительных ролях EventRoleSlot
    """
    return Q(responsible=user) | Q(s_engineer=user) | Q(engineers=user) | Q(role_slots__users=user)


# =========================
# views
# =========================

@login_required
def calendar_view(request: HttpRequest) -> HttpResponse:
    auto_close_past_events()

    year, month = _parse_year_month(request)
    cal_filter = (request.GET.get("filter") or "all").strip()
    if cal_filter not in {"all", "confirmed", "mine"}:
        cal_filter = "all"

    month_days = list(pycalendar.Calendar(firstweekday=0).monthdatescalendar(year, month))
    grid_start = month_days[0][0]
    grid_end = month_days[-1][-1]

    qs = (
        Event.objects.filter(is_deleted=False)
        .filter(start_date__lte=grid_end, end_date__gte=grid_start)
        .select_related("responsible", "s_engineer")
        .prefetch_related("engineers")
        .order_by("start_date", "id")
    )

    can_view_all = _can_view_all_events(request.user)

    # 🔒 Ограничение видимости для всех ролей, кроме менеджера/старшего инженера
    if not can_view_all:
        qs = qs.filter(_participation_q(request.user)).distinct()
        # фильтр "all" для них фактически превращаем в "mine", чтобы не путать
        cal_filter = "mine"

    # Фильтры
    if cal_filter == "confirmed":
        qs = qs.filter(status="confirmed")
    elif cal_filter == "mine":
        qs = qs.filter(_participation_q(request.user)).distinct()

    event_problem = {e.id: bool(calculate_shortages(e)) for e in qs}

    week_segments: dict[date, list[dict]] = {}
    for week in month_days:
        ws = week[0]
        we = week[-1]
        segs: list[dict] = []
        for e in qs:
            seg_start = max(e.start_date, ws, grid_start)
            seg_end = min(e.end_date, we, grid_end)
            if seg_end < seg_start:
                continue
            start_col = week.index(seg_start)
            end_col = week.index(seg_end)
            segs.append({
                "event": e,
                "start_col": start_col,
                "end_col": end_col,
                "span": (end_col - start_col + 1),
                "cont_left": e.start_date < ws,
                "cont_right": e.end_date > we,
                "has_problem": event_problem.get(e.id, False),
                "data_start": e.start_date.strftime("%Y-%m-%d"),
                "data_end": e.end_date.strftime("%Y-%m-%d"),
            })
        week_segments[ws] = _pack_lanes(segs)

    return render(request, "events/calendar.html", {
        "year": year,
        "month": month,
        "month_name": pycalendar.month_name[month],
        "month_days": month_days,
        "week_segments": week_segments,
        "filter": cal_filter,
        "can_create_event": can_edit_event_card(request.user),
        "can_view_all_events": can_view_all,
    })


@login_required
def event_list_view(request: HttpRequest) -> HttpResponse:

    today = timezone.localdate()

    qs = (
        Event.objects.filter(is_deleted=False)
        .select_related("responsible", "s_engineer")
        .prefetch_related("engineers", "role_slots__role", "role_slots__users")
    )

    can_view_all = _can_view_all_events(request.user)
    if not can_view_all:
        qs = qs.filter(_participation_q(request.user)).distinct()

    # Прошедшие/закрытые:
    # - закрытые и отменённые всегда туда
    # - или те, у которых дата окончания < сегодня
    past_q = (
        Q(status__in=[Event.STATUS_CLOSED, Event.STATUS_CANCELLED])
        | Q(end_date__lt=today)
        | (Q(end_date__isnull=True) & Q(start_date__lt=today))
    )

    past_events = qs.filter(past_q).distinct().order_by("-start_date", "-id")
    upcoming_events = qs.exclude(past_q).distinct().order_by("start_date", "id")

    return render(
        request,
        "events/event_list.html",
        {
            "upcoming_events": upcoming_events,
            "past_events": past_events,
            "past_count": past_events.count(),
            "can_create_event": can_edit_event_card(request.user),
            "can_delete": can_edit_event_card(request.user),
            "can_edit": can_edit_event_card(request.user),
            "can_view_all_events": can_view_all,
        },
    )


@login_required
def event_detail_view(request: HttpRequest, event_id: int) -> HttpResponse:
    can_manage = can_edit_event_card(request.user)
    can_view_all = _can_view_all_events(request.user)

    base_qs = (Event.objects.select_related("responsible", "s_engineer").prefetch_related("engineers", "role_slots__role", "role_slots__users"))

    # Обычным пользователям нельзя видеть удалённые события
    if not can_manage:
        base_qs = base_qs.filter(is_deleted=False)

    # 🔒 Ограничение доступа к карточке: не-менеджер/не-старший видит только “свои”
    if not can_view_all:
        base_qs = base_qs.filter(is_deleted=False).filter(_participation_q(request.user)).distinct()

    event = get_object_or_404(base_qs, id=event_id)

    equipment_items = EventEquipment.objects.filter(event=event).select_related("equipment").order_by("equipment__name")
    rented_items = EventRentedEquipment.objects.filter(event=event).select_related("equipment").order_by("equipment__name")
    shortages = calculate_shortages(event)

    stock_reservations = (
        EventStockReservation.objects.filter(event=event)
        .select_related("equipment_type", "equipment_type__category", "equipment_type__subcategory")
        .order_by("equipment_type__category__name", "equipment_type__subcategory__name", "equipment_type__name", "id")
    )

    stock_rows = []
    stock_shortages = []
    for r in stock_reservations:
        available = _stock_available_for_event(event, r.equipment_type, exclude_event_id=event.id)
        # available = максимальное количество, которое можно забронировать ЭТОМУ событию на его даты,
        # если игнорировать его же бронь (то есть total_physical - reserved_other).
        shortage = max(0, r.quantity - available)
        stock_rows.append({
            "reservation": r,
            "available": available,
            "shortage": shortage,
        })
        if shortage > 0:
            stock_shortages.append({
                "type": r.equipment_type,
                "required": r.quantity,
                "available": available,
                "shortage": shortage,
            })

    return render(request, "events/event_detail.html", {
        "event": event,
        "equipment_items": equipment_items,
        "rented_items": rented_items,
        "shortages": shortages,
        "stock_rows": stock_rows,
        "stock_shortages": stock_shortages,
        "can_modify": can_manage,
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
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    event = get_object_or_404(Event, id=event_id)

    if event.is_deleted:
        return HttpResponseForbidden("Нельзя редактировать удалённое мероприятие")

    # ✅ ВАЖНО: instance=event
    form = EventForm(request.POST or None, instance=event)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Мероприятие обновлено.")
            return redirect("event_detail", event_id=event.id)
        messages.error(request, "Исправьте ошибки формы.")

    return render(
        request,
        "events/event_form.html",
        {
            "title": "Редактировать мероприятие",
            "form": form,
        },
    )


@login_required
def event_set_status_view(request: HttpRequest, event_id: int, status: str) -> HttpResponse:
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")
    event = get_object_or_404(Event, id=event_id, is_deleted=False)

    allowed = {"draft", "confirmed", "cancelled", "closed"}
    if status not in allowed:
        messages.error(request, "Некорректный статус.")
        return redirect("event_detail", event_id=event.id)

    event.status = status
    event.save(update_fields=["status"])
    log_action(user=request.user, action="status", obj=event, details=f"Статус: {status}")
    messages.success(request, "Статус обновлён.")
    return redirect("event_detail", event_id=event.id)


# ---- soft delete / trash ----

@login_required
def event_delete_view(request: HttpRequest, event_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseForbidden("POST only")
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    event = get_object_or_404(Event, id=event_id, is_deleted=False)
    event.is_deleted = True
    event.deleted_at = timezone.now()
    event.save(update_fields=["is_deleted", "deleted_at"])
    log_action(user=request.user, action="delete", obj=event, details="Удалено (в корзину)")
    messages.success(request, "Мероприятие перемещено в корзину.")
    return redirect("event_list")


@login_required
def event_trash_view(request: HttpRequest) -> HttpResponse:
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")
    qs = (
        Event.objects.filter(is_deleted=True)
        .select_related("responsible", "s_engineer")
        .prefetch_related("engineers")
        .order_by("-deleted_at", "-id")
    )
    return render(request, "events/event_trash.html", {"events": qs})


@login_required
def event_restore_view(request: HttpRequest, event_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseForbidden("POST only")
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")
    event = get_object_or_404(Event, id=event_id)
    event.is_deleted = False
    event.deleted_at = None
    event.save(update_fields=["is_deleted", "deleted_at"])
    log_action(user=request.user, action="restore", obj=event, details="Восстановлено из корзины")
    messages.success(request, "Мероприятие восстановлено.")
    return redirect("event_trash")


@login_required
def event_purge_view(request: HttpRequest, event_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseForbidden("POST only")
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")
    event = get_object_or_404(Event, id=event_id)
    if not event.is_deleted:
        messages.error(request, "Нельзя удалить навсегда: событие не в корзине.")
        return redirect("event_list")
    obj_repr = str(event)
    event.delete()
    try:
        log_action(user=request.user, action="purge", entity_type="Event", message=f"Удалено навсегда: {obj_repr}")
    except Exception:
        pass
    messages.success(request, "Мероприятие удалено навсегда.")
    return redirect("event_trash")


# ---- equipment ----

@login_required
def event_equipment_add_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EventEquipmentForm(request.POST, event=event)
        if form.is_valid():
            equipment = form.cleaned_data["equipment"]
            qty = int(form.cleaned_data.get("quantity") or 0)
            if qty <= 0:
                return redirect("event_detail", event_id=event.id)
            item, created = EventEquipment.objects.get_or_create(event=event, equipment=equipment, defaults={"quantity": 0})
            item.quantity = (item.quantity or 0) + qty if not created else qty
            item.save(update_fields=["quantity"])
            messages.success(request, "Оборудование добавлено.")
            return redirect("event_detail", event_id=event.id)
    else:
        form = EventEquipmentForm(event=event)

    return render(request, "events/event_equipment_add.html", {"event": event, "form": form})


@login_required
def event_equipment_update_qty_view(request: HttpRequest, event_id: int, item_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
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
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")
    item = get_object_or_404(EventEquipment, id=item_id, event=event)
    if request.method == "POST":
        item.delete()
    return redirect("event_detail", event_id=event.id)


# ---- rented ----

@login_required
def event_rented_add_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
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
            item, created = EventRentedEquipment.objects.get_or_create(event=event, equipment=equipment, defaults={"quantity": 0})
            item.quantity = (item.quantity or 0) + qty if not created else qty
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
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
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
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")
    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)
    if request.method == "POST":
        item.delete()
    return redirect("event_detail", event_id=event.id)


# ---- stock (warehouse) reservations: phase 1 ----

@login_required
def event_stock_add_view(request: HttpRequest, event_id: int) -> HttpResponse:
    """Добавить/увеличить бронь по типу склада на даты мероприятия."""
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    q = (request.GET.get("q") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    subcategory_id = (request.GET.get("subcategory") or "").strip()

    types_qs = StockEquipmentType.objects.filter(is_active=True).select_related("category", "subcategory")
    if q:
        types_qs = types_qs.filter(
            Q(name__icontains=q)
            | Q(category__name__icontains=q)
            | Q(subcategory__name__icontains=q)
        )
    if category_id.isdigit():
        types_qs = types_qs.filter(category_id=int(category_id))
    if subcategory_id.isdigit():
        types_qs = types_qs.filter(subcategory_id=int(subcategory_id))

    types_qs = types_qs.order_by("category__name", "subcategory__name", "name", "id")

    if request.method == "POST":
        form = EventStockReservationForm(request.POST, event=event)
        if form.is_valid():
            eq_type = form.cleaned_data["equipment_type"]
            qty_add = int(form.cleaned_data.get("quantity") or 0)
            if qty_add <= 0:
                return redirect("event_detail", event_id=event.id)

            res, created = EventStockReservation.objects.get_or_create(
                event=event,
                equipment_type=eq_type,
                defaults={"quantity": 0, "created_by": request.user},
            )
            # если запись уже была — created_by не трогаем
            new_qty = (res.quantity or 0) + qty_add

            max_allowed = _stock_available_for_event(event, eq_type, exclude_event_id=event.id)
            if new_qty > max_allowed:
                messages.error(
                    request,
                    f"Нельзя забронировать {new_qty} шт. Доступно на эти даты: {max_allowed}.",
                )
            else:
                res.quantity = new_qty
                if created and not res.created_by_id:
                    res.created_by = request.user
                res.save(update_fields=["quantity", "created_by"] if created else ["quantity"])
                messages.success(request, "Бронь по складу сохранена.")
                return redirect("event_detail", event_id=event.id)
        else:
            messages.error(request, "Исправьте ошибки в форме")
    else:
        form = EventStockReservationForm(event=event)

    # уже забронировано этим событием
    existing = (
        EventStockReservation.objects.filter(event=event)
        .select_related("equipment_type", "equipment_type__category", "equipment_type__subcategory")
        .order_by("equipment_type__category__name", "equipment_type__subcategory__name", "equipment_type__name")
    )

    # строки типов с доступностью
    type_rows = []
    for t in types_qs[:300]:  # не грузим бесконечно
        available = _stock_available_for_event(event, t, exclude_event_id=event.id)
        type_rows.append({"type": t, "available": available})

    # фильтры категорий/подкатегорий
    from inventory.models import StockCategory, StockSubcategory
    categories = StockCategory.objects.all().order_by("name")
    subcats = StockSubcategory.objects.all().order_by("category__name", "name")
    if category_id.isdigit():
        subcats = subcats.filter(category_id=int(category_id))

    return render(
        request,
        "events/event_stock_add.html",
        {
            "event": event,
            "form": form,
            "existing": existing,
            "type_rows": type_rows,
            "q": q,
            "categories": categories,
            "subcategories": subcats,
            "category_id": category_id,
            "subcategory_id": subcategory_id,
        },
    )


@login_required
def event_stock_update_qty_view(request: HttpRequest, event_id: int, reservation_id: int) -> HttpResponse:
    """Изменить количество брони (0 = удалить)."""
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    res = get_object_or_404(
        EventStockReservation.objects.select_related("equipment_type"),
        id=reservation_id,
        event=event,
    )

    if request.method == "POST":
        qty = _safe_int(request.POST.get("quantity"), 0)
        if qty <= 0:
            res.delete()
            messages.success(request, "Бронь удалена")
        else:
            max_allowed = _stock_available_for_event(event, res.equipment_type, exclude_event_id=event.id)
            if qty > max_allowed:
                messages.error(request, f"Нельзя поставить {qty}. Доступно на эти даты: {max_allowed}.")
            else:
                res.quantity = qty
                res.save(update_fields=["quantity"])
                messages.success(request, "Бронь обновлена")

    return redirect("event_detail", event_id=event.id)


@login_required
def event_stock_delete_view(request: HttpRequest, event_id: int, reservation_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
    if not can_edit_event_equipment(request.user):
        return HttpResponseForbidden("Недостаточно прав")
    res = get_object_or_404(EventStockReservation, id=reservation_id, event=event)
    if request.method == "POST":
        res.delete()
        messages.success(request, "Бронь удалена")
    return redirect("event_detail", event_id=event.id)


# ---- API ----

@transaction.atomic
@login_required
def quick_create_event_api(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"})

    if not can_edit_event_card(request.user):
        return JsonResponse({"ok": False, "error": "Недостаточно прав"})

    try:
        import json
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Bad JSON"})

    name = (payload.get("name") or "").strip()
    start_date_str = (payload.get("start_date") or "").strip()
    end_date_str = (payload.get("end_date") or "").strip()
    notes = (payload.get("notes") or "").strip()

    if not name:
        return JsonResponse({"ok": False, "error": "Название обязательно"})

    try:
        sd = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректная дата начала"})

    if end_date_str:
        try:
            ed = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except Exception:
            return JsonResponse({"ok": False, "error": "Некорректная дата окончания"})
    else:
        ed = sd

    if ed < sd:
        return JsonResponse({"ok": False, "error": "Дата окончания раньше даты начала"})

    event = Event.objects.create(
        name=name,
        start_date=sd,
        end_date=ed,
        status=Event.STATUS_DRAFT,
        responsible=request.user,
        notes=notes,
    )

    log_action(user=request.user, action="create", obj=event, details="Создано мероприятие (календарь)")
    return JsonResponse({"ok": True, "id": event.id})


@login_required
def quick_move_event_api(request: HttpRequest, event_id: int) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"}, status=405)

    if not can_edit_event_card(request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    event = get_object_or_404(Event, id=event_id, is_deleted=False)

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
