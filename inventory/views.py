from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from events.models import EventEquipment
from .models import Equipment, EquipmentCategory


def _parse_dt(value: str):
    """
    Парсим datetime-local из формы: 'YYYY-MM-DDTHH:MM'
    Возвращаем aware datetime (если USE_TZ=True), иначе naive.
    """
    if not value:
        return None

    dt = datetime.fromisoformat(value)
    if timezone.is_naive(dt):
        try:
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        except Exception:
            pass
    return dt


def _reserved_map(start_dt, end_dt):
    """
    Сколько занято на период start_dt..end_dt по каждому equipment_id.
    """
    reserved = (
        EventEquipment.objects
        .filter(event__date_start__lt=end_dt, event__date_end__gt=start_dt)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {row['equipment_id']: (row['total'] or 0) for row in reserved}


@login_required
def equipment_list_all_view(request):
    """
    Полный список оборудования.
    Если передан период (start/end) — считаем свободно на период.
    """
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')

    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)

    equipments = Equipment.objects.select_related('category').order_by('category__name', 'name')

    availability = {}
    if start_dt and end_dt:
        reserved = _reserved_map(start_dt, end_dt)
        for eq in equipments:
            used = int(reserved.get(eq.id, 0) or 0)
            free = eq.quantity_total - used
            if free < 0:
                free = 0
            availability[eq.id] = free

    return render(request, 'inventory/equipment_list_all.html', {
        'equipments': equipments,
        'start': start,
        'end': end,
        'availability': availability,
    })


@login_required
def equipment_list_categories_view(request):
    """
    Просмотр по категориям.
    Возвращаем:
    - categories: список категорий
    - by_category: {category_id: [Equipment, ...]}
    - availability: {equipment_id: free_on_period}
    """
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')

    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)

    categories = EquipmentCategory.objects.all().order_by('name')
    equipments = Equipment.objects.select_related('category').order_by('category__name', 'name')

    availability = {}
    if start_dt and end_dt:
        reserved = _reserved_map(start_dt, end_dt)
        for eq in equipments:
            used = int(reserved.get(eq.id, 0) or 0)
            free = eq.quantity_total - used
            if free < 0:
                free = 0
            availability[eq.id] = free

    by_category = {}
    for eq in equipments:
        by_category.setdefault(eq.category_id, []).append(eq)

    return render(request, 'inventory/equipment_list_categories.html', {
        'categories': categories,
        'by_category': by_category,
        'start': start,
        'end': end,
        'availability': availability,
    })


@login_required
def equipment_detail_view(request, equipment_id):
    equipment = get_object_or_404(Equipment.objects.select_related('category'), id=equipment_id)

    return render(request, 'inventory/equipment_detail.html', {
        'equipment': equipment,
    })
