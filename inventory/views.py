from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from events.models import EventEquipment
from .models import Equipment, EquipmentCategory


def _parse_dt(value: str):
    if not value:
        return None
    dt = datetime.fromisoformat(value)  # "YYYY-MM-DDTHH:MM"
    if timezone.is_naive(dt):
        try:
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        except Exception:
            pass
    return dt


def _reserved_map(start_dt, end_dt):
    reserved = (
        EventEquipment.objects
        .filter(event__date_start__lt=end_dt, event__date_end__gt=start_dt)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {row['equipment_id']: int(row['total'] or 0) for row in reserved}


def _rows_with_free(equipments, start_dt, end_dt):
    """
    Возвращает список строк для таблицы:
    [
      {"equipment": eq, "free": free_or_None}
    ]
    """
    rows = []
    free_map = None

    if start_dt and end_dt:
        free_map = {}
        reserved = _reserved_map(start_dt, end_dt)
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
    """
    Страница категорий (кликабельных).
    """
    categories = EquipmentCategory.objects.all().order_by('name')
    return render(request, 'inventory/equipment_list_categories.html', {
        "categories": categories,
    })


@login_required
def equipment_list_all_view(request):
    """
    Весь список оборудования.
    Можно выбрать период, чтобы видеть 'свободно на период'.
    """
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')

    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)

    equipments = Equipment.objects.select_related('category').order_by('category__name', 'name')
    rows = _rows_with_free(equipments, start_dt, end_dt)

    return render(request, 'inventory/equipment_list_all.html', {
        "rows": rows,
        "start": start,
        "end": end,
        "has_period": bool(start_dt and end_dt),
    })


@login_required
def equipment_category_view(request, category_id):
    """
    Оборудование внутри выбранной категории.
    """
    category = get_object_or_404(EquipmentCategory, id=category_id)

    start = request.GET.get('start', '')
    end = request.GET.get('end', '')

    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)

    equipments = (
        Equipment.objects
        .filter(category=category)
        .select_related('category')
        .order_by('name')
    )
    rows = _rows_with_free(equipments, start_dt, end_dt)

    return render(request, 'inventory/equipment_category.html', {
        "category": category,
        "rows": rows,
        "start": start,
        "end": end,
        "has_period": bool(start_dt and end_dt),
    })


@login_required
def equipment_detail_view(request, equipment_id):
    equipment = get_object_or_404(Equipment.objects.select_related('category'), id=equipment_id)
    return render(request, 'inventory/equipment_detail.html', {
        "equipment": equipment,
    })
