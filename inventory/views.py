from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

from accounts.permissions import user_can_edit
from .models import EquipmentCategory, Equipment
from .forms import EquipmentForm

from events.models import EventEquipment


@login_required
def equipment_list_view(request):
    mode = request.GET.get('mode', 'categories')  # 'categories' | 'all'
    can_edit = user_can_edit(request.user)

    categories = EquipmentCategory.objects.all().order_by('name')

    if mode == 'all':
        items = Equipment.objects.select_related('category').order_by('category__name', 'name')
        return render(request, 'inventory/equipment_list_all.html', {
            'mode': mode,
            'can_edit': can_edit,
            'categories': categories,
            'items': items,
        })

    category_id = request.GET.get('category')
    selected_category = None
    items = Equipment.objects.none()

    if category_id:
        selected_category = get_object_or_404(EquipmentCategory, id=category_id)
        items = Equipment.objects.filter(category=selected_category).order_by('name')

    return render(request, 'inventory/equipment_list_categories.html', {
        'mode': mode,
        'can_edit': can_edit,
        'categories': categories,
        'selected_category': selected_category,
        'items': items,
    })


@login_required
def equipment_detail_view(request, equipment_id):
    can_edit = user_can_edit(request.user)
    equipment = get_object_or_404(Equipment.objects.select_related('category'), id=equipment_id)

    bookings = (
        EventEquipment.objects
        .filter(equipment=equipment)
        .select_related('event')
        .order_by('-event__date_start')
    )

    return render(request, 'inventory/equipment_detail.html', {
        'can_edit': can_edit,
        'equipment': equipment,
        'bookings': bookings,
    })


@login_required
def equipment_create_view(request):
    if not user_can_edit(request.user):
        return HttpResponseForbidden('Недостаточно прав')

    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return redirect('equipment_detail', equipment_id=obj.id)
    else:
        form = EquipmentForm()

    return render(request, 'inventory/equipment_form.html', {
        'title': 'Добавить оборудование',
        'form': form,
    })


@login_required
def equipment_update_view(request, equipment_id):
    if not user_can_edit(request.user):
        return HttpResponseForbidden('Недостаточно прав')

    equipment = get_object_or_404(Equipment, id=equipment_id)

    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=equipment)
        if form.is_valid():
            obj = form.save()
            return redirect('equipment_detail', equipment_id=obj.id)
    else:
        form = EquipmentForm(instance=equipment)

    return render(request, 'inventory/equipment_form.html', {
        'title': 'Редактировать оборудование',
        'form': form,
    })
