from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django import forms

from accounts.permissions import can_edit_inventory
from .models import Equipment, EquipmentCategory
from django.db.models.deletion import ProtectedError
from django.contrib import messages

# ---------- Forms (просто и надёжно, без отдельного forms.py) ----------

class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ["name", "category", "serial_number", "quantity_total", "location", "status", "notes"]


class CategoryForm(forms.ModelForm):
    class Meta:
        model = EquipmentCategory
        fields = ["name"]


# ---------- Views ----------

@login_required
def equipment_list_all_view(request):
    equipment = (
        Equipment.objects
        .select_related("category")
        .order_by("category__name", "name")
    )

    return render(request, "inventory/equipment_list_all.html", {
        "equipment": equipment,
        "can_manage": can_edit_inventory(request.user),
    })


@login_required
def equipment_list_categories_view(request):
    categories = EquipmentCategory.objects.order_by("name")
    return render(request, "inventory/equipment_list_categories.html", {
        "categories": categories,
        "can_manage": can_edit_inventory(request.user),
    })


@login_required
def equipment_category_detail_view(request, category_id):
    category = get_object_or_404(EquipmentCategory, id=category_id)
    equipment = (
        Equipment.objects
        .filter(category=category)
        .order_by("name")
    )

    return render(request, "inventory/equipment_category_detail.html", {
        "category": category,
        "equipment": equipment,
        "can_manage": can_edit_inventory(request.user),
    })


# ---------- CRUD Equipment ----------

@login_required
def equipment_create_view(request):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EquipmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("equipment_list_all")
    else:
        form = EquipmentForm()

    return render(request, "inventory/equipment_form.html", {
        "form": form,
        "title": "Добавить оборудование",
    })


@login_required
def equipment_update_view(request, equipment_id):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    obj = get_object_or_404(Equipment, id=equipment_id)

    if request.method == "POST":
        form = EquipmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("equipment_list_all")
    else:
        form = EquipmentForm(instance=obj)

    return render(request, "inventory/equipment_form.html", {
        "form": form,
        "title": "Редактировать оборудование",
    })


@login_required
def equipment_delete_view(request, equipment_id):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    obj = get_object_or_404(Equipment, id=equipment_id)

    if request.method == "POST":
        obj.delete()
        return redirect("equipment_list_all")

    return render(request, "inventory/equipment_confirm_delete.html", {
        "equipment": obj,
    })


# ---------- CRUD Category ----------

@login_required
def category_create_view(request):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("equipment_list_categories")
    else:
        form = CategoryForm()

    return render(request, "inventory/category_form.html", {
        "form": form,
        "title": "Добавить категорию",
    })


@login_required
def category_update_view(request, category_id):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    category = get_object_or_404(EquipmentCategory, id=category_id)

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect("equipment_list_categories")
    else:
        form = CategoryForm(instance=category)

    return render(request, "inventory/category_form.html", {
        "form": form,
        "title": "Редактировать категорию",
    })


@login_required
def category_delete_view(request, equipment_id):
    equipment = get_object_or_404(Equipment, id=equipment_id)

    # ...проверка прав...

    if request.method == "POST":
        try:
            equipment.delete()
            messages.success(request, "Оборудование удалено.")
        except ProtectedError:
            messages.error(
                request,
                "Нельзя удалить: оборудование уже используется в мероприятиях. "
                "Лучше архивировать (скроем из списка, но оставим в истории)."
            )
        return redirect("equipment_list_all")  # или твой актуальный name

