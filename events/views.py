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


def _pack_lanes(segments: list[dict]) -> list[dict]:
    """
    Раскладываем сегменты недели по "линиям" (lane), чтобы они не пересекались по колонкам.
    seg: {"start_col": int, "end_col": int, ...}
    """
    lanes: list[list[tuple[int, int]]] = []

    for seg in sorted(segments, key=lambda s: (s["start_col"], s["end_col"], s["event"].id)):
        placed = False

        for lane_idx, used in enumerate(lanes):
            conflict = False
            for a, b in used:
                if not (seg["end_col"] < a or seg["start_col"] > b):
                    conflict = True
                    break
            if not conflict:
                seg["lane"] = lane_idx
                used.append((seg["start_col"], seg["end_col"]))
                placed = True
                break

        if not placed:
            seg["lane"] = len(lanes)
            lanes.append([(seg["start_col"], seg["end_col"])])

    return segments


@login_required
def calendar_view(request: HttpRequest) -> HttpResponse:
    auto_close_past_events()

    year, month = _parse_year_month(request)
    cal_filter = (request.GET.get("filter") or "all").strip()
    if cal_filter not in {"all", "confirmed", "mine"}:
        cal_filter = "all"

    # Сетка календаря (включая дни соседних месяцев)
    month_days = list(pycalendar.Calendar(firstweekday=0).monthdatescalendar(year, month))
    grid_start = month_days[0][0]
    grid_end = month_days[-1][-1]

    qs = (
        Event.objects
        .filter(start_date__lte=grid_end, end_date__gte=grid_start, is_deleted=False)
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

    # “не всё ок”
    event_problem: dict[int, bool] = {}
    for e in qs:
        event_problem[e.id] = bool(calculate_shortages(e))

    # Ключ: week_start(date) -> список сегментов на эту неделю
    week_segments: dict[date, list[dict]] = {}

    for week in month_days:
        week_start = week[0]
        week_end = week[-1]

        segs: list[dict] = []

        for e in qs:
            # пересечение события с неделей (в пределах видимой сетки)
            seg_start = max(e.start_date, week_start, grid_start)
            seg_end = min(e.end_date, week_end, grid_end)
            if seg_end < seg_start:
                continue

            start_col = week.index(seg_start)  # 0..6
            end_col = week.index(seg_end)

            segs.append({
                "event": e,
                "start_col": start_col,
                "end_col": end_col,
                "span": (end_col - start_col + 1),

                "cont_left": e.start_date < week_start,   # продолжается из прошлой недели
                "cont_right": e.end_date > week_end,      # уходит в следующую неделю

                "has_problem": event_problem.get(e.id, False),

                "data_start": e.start_date.strftime("%Y-%m-%d"),
                "data_end": e.end_date.strftime("%Y-%m-%d"),
            })

        segs = _pack_lanes(segs)
        week_segments[week_start] = segs

    ctx = {
        "year": year,
        "month": month,
        "month_name": pycalendar.month_name[month],
        "month_days": month_days,

        # важно: теперь календарь рисуем по сегментам
        "week_segments": week_segments,

        "filter": cal_filter,
        "can_create_event": can_edit_event_card(request.user),
        "can_edit": can_edit_event_card(request.user),
        "can_delete": can_edit_event_card(request.user),
    }
    return render(request, "events/calendar.html", ctx)


@login_required
def event_list_view(request: HttpRequest) -> HttpResponse:
    qs = (
        Event.objects.filter(is_deleted=False)
        .select_related("responsible", "s_engineer")
        .prefetch_related("engineers")
        .order_by("-start_date", "-id")
    )
    return render(request, "events/event_list.html", {
        "events": qs,
        "can_create_event": can_edit_event_card(request.user),
        "can_edit": can_edit_event_card(request.user),
        "can_delete": can_edit_event_card(request.user),
    })


@login_required
def event_detail_view(request: HttpRequest, event_id: int) -> HttpResponse:
    """
    Важно: удалённые (soft-delete) события должны открываться из корзины.
    Но показываем их только тем, кто имеет право управлять мероприятиями.
    """
    # менеджер/суперадмин
    can_manage = can_edit_event_card(request.user)

    # если soft-delete поля существуют, то:
    # - обычные пользователи НЕ должны открывать удалённые события
    # - менеджеры могут (нужно для корзины)
    base_qs = Event.objects.select_related("responsible", "s_engineer").prefetch_related("engineers")

    try:
        # если в модели есть is_deleted, ограничим для не-менеджеров
        if hasattr(Event, "is_deleted") and not can_manage:
            base_qs = base_qs.filter(is_deleted=False)
    except Exception:
        pass

    event = get_object_or_404(base_qs, id=event_id)

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
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
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

@login_required
def event_delete_view(request: HttpRequest, event_id: int) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        event.is_deleted = True
        event.deleted_at = timezone.now()
        event.save(update_fields=["is_deleted", "deleted_at"])
        log_action(user=request.user, action="delete", obj=event, details="Soft-delete мероприятия")
        messages.success(request, "Мероприятие удалено (перемещено в архив).")
        return redirect("event_list")

    return render(request, "events/event_confirm_delete.html", {"event": event})


def event_set_status_view(request: HttpRequest, event_id: int, status: str) -> HttpResponse:
    event = get_object_or_404(Event, id=event_id, is_deleted=False)
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

from django.utils import timezone

@login_required
def event_trash_view(request: HttpRequest) -> HttpResponse:
    # только те, кто может править карточки (у тебя это менеджер/суперадмин)
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    deleted_qs = (
        Event.objects
        .filter(is_deleted=True)
        .select_related("responsible", "s_engineer")
        .prefetch_related("engineers")
        .order_by("-deleted_at", "-id")
    )

    return render(request, "events/event_trash.html", {
        "events": deleted_qs,
        "can_restore": True,
    })


@login_required
def event_restore_view(request: HttpRequest, event_id: int) -> HttpResponse:
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    event = get_object_or_404(Event, id=event_id)

    if request.method != "POST":
        return HttpResponseForbidden("POST only")

    # восстановление
    event.is_deleted = False
    event.deleted_at = None
    event.save(update_fields=["is_deleted", "deleted_at"])

    try:
        log_action(user=request.user, action="restore", obj=event, details="Восстановлено из корзины")
    except Exception:
        pass

    messages.success(request, "Мероприятие восстановлено.")
    return redirect("event_trash")

@login_required
def event_delete_view(request: HttpRequest, event_id: int) -> HttpResponse:
    """
    Мягкое удаление: мероприятие попадает в корзину.
    """
    if request.method != "POST":
        return HttpResponseForbidden("POST only")

    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    event = get_object_or_404(Event, id=event_id)

    # если soft-delete полей нет — fallback на hard delete
    if not hasattr(event, "is_deleted"):
        event.delete()
        messages.success(request, "Мероприятие удалено.")
        return redirect("event_list")

    event.is_deleted = True
    event.deleted_at = timezone.now()
    event.save(update_fields=["is_deleted", "deleted_at"])

    try:
        log_action(user=request.user, action="delete", obj=event, details="Удалено (в корзину)")
    except Exception:
        pass

    messages.success(request, "Мероприятие перемещено в корзину.")
    return redirect("event_list")


@login_required
def event_trash_view(request: HttpRequest) -> HttpResponse:
    """
    Корзина: видят только менеджер/суперадмин.
    """
    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    # если soft-delete нет — корзину не показываем
    if not hasattr(Event, "is_deleted"):
        messages.info(request, "Корзина недоступна: soft-delete не включён.")
        return redirect("event_list")

    deleted_qs = (
        Event.objects
        .filter(is_deleted=True)
        .select_related("responsible", "s_engineer")
        .prefetch_related("engineers")
        .order_by("-deleted_at", "-id")
    )

    return render(request, "events/event_trash.html", {"events": deleted_qs})


@login_required
def event_restore_view(request: HttpRequest, event_id: int) -> HttpResponse:
    """
    Восстановление из корзины.
    """
    if request.method != "POST":
        return HttpResponseForbidden("POST only")

    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if not hasattr(Event, "is_deleted"):
        return HttpResponseForbidden("Soft-delete не включён")

    event = get_object_or_404(Event, id=event_id)

    event.is_deleted = False
    event.deleted_at = None
    event.save(update_fields=["is_deleted", "deleted_at"])

    try:
        log_action(user=request.user, action="restore", obj=event, details="Восстановлено из корзины")
    except Exception:
        pass

    messages.success(request, "Мероприятие восстановлено.")
    return redirect("event_trash")


@login_required
def event_purge_view(request: HttpRequest, event_id: int) -> HttpResponse:
    """
    Жёсткое удаление навсегда. Только из корзины.
    """
    if request.method != "POST":
        return HttpResponseForbidden("POST only")

    if not can_edit_event_card(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    event = get_object_or_404(Event, id=event_id)

    # разрешаем purge только если soft-delete и is_deleted=True
    if hasattr(event, "is_deleted") and not event.is_deleted:
        messages.error(request, "Нельзя удалить навсегда: мероприятие не в корзине.")
        return redirect("event_list")

    try:
        obj_repr = str(event)
    except Exception:
        obj_repr = f"id={event_id}"

    event.delete()

    try:
        log_action(user=request.user, action="purge", entity_type="Event", message=f"Удалено навсегда: {obj_repr}")
    except Exception:
        pass

    messages.success(request, "Мероприятие удалено навсегда.")
    return redirect("event_trash")