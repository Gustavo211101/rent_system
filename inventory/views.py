from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404, render

from events.models import EventEquipment
from .models import Equipment, EquipmentCategory


def _parse_date(value: str):
    if not value:
        return None
    # ожидаем YYYY-MM-DD
    try:
        y, m, d = value.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def _overlap_q(prefix: str, start: date, end: date) -> Q:
    # start_date <= end AND (end_date >= start OR end_date is null and start_date >= start)
    return (
        Q(**{f"{prefix}start_date__lte": end})
        & (
            Q(**{f"{prefix}end_date__gte": start})
            | (Q(**{f"{prefix}end_date__isnull": True}) & Q(**{f"{prefix}start_date__gte": start}))
        )
    )


def _reserved_map(start_d: date, end_d: date):
    reserved = (
        EventEquipment.objects
        .filter(_overlap_q("event__", start_d, end_d))
        .values("equipment_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["equipment_id"]: int(row["total"] or 0) for row in reserved}


def _rows_with_free(equipments, start_d, end_d):
    rows = []
    free_map = None

    if start_d and end_d:
        reserved = _reserved_map(start_d, end_d)
        free_map = {}
        for eq in equipments:
            used = reserved.get(eq.id, 0)
            free = eq.quantity_total - used
            if free < 0:
                free = 0
            free_map[eq.id] = free

    for eq in equipments:
        rows.append({
            "equipment": eq,
            "free": None if free_map is None else free_map.get(eq.id, 0),
        })

    return rows


@login_required
def equipment_list_categories_view(request):
    categories = EquipmentCategory.objects.all().order_by("name")
    return render(request, "inventory/equipment_list_categories.html", {
        "categories": categories,
    })


@login_required
def equipment_list_all_view(request):
    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()

    start_d = _parse_date(start)
    end_d = _parse_date(end)

    equipments = Equipment.objects.select_related("category").order_by("category__name", "name")
    rows = _rows_with_free(equipments, start_d, end_d)

    return render(request, "inventory/equipment_list_all.html", {
        "rows": rows,
        "start": start,
        "end": end,
        "has_period": bool(start_d and end_d),
    })


@login_required
def equipment_category_view(request, category_id):
    category = get_object_or_404(EquipmentCategory, id=category_id)

    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()

    start_d = _parse_date(start)
    end_d = _parse_date(end)

    equipments = (
        Equipment.objects
        .filter(category=category)
        .select_related("category")
        .order_by("name")
    )
    rows = _rows_with_free(equipments, start_d, end_d)

    return render(request, "inventory/equipment_category.html", {
        "category": category,
        "rows": rows,
        "start": start,
        "end": end,
        "has_period": bool(start_d and end_d),
    })


@login_required
def equipment_detail_view(request, equipment_id):
    equipment = get_object_or_404(Equipment.objects.select_related("category"), id=equipment_id)
    return render(request, "inventory/equipment_detail.html", {
        "equipment": equipment,
    })