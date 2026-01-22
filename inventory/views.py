from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import can_edit_inventory
from audit.utils import log_action
from .models import Equipment, EquipmentCategory


# ---------- Forms (просто и надёжно) ----------

class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ["name", "category", "serial_number", "quantity_total", "location", "status", "notes"]


class CategoryForm(forms.ModelForm):
    class Meta:
        model = EquipmentCategory
        fields = ["name"]


# ---------- Views (просмотр) ----------

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
            obj = form.save()
            log_action(user=request.user, action="create", obj=obj, details="Создано оборудование")
            messages.success(request, "Оборудование добавлено.")
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
            obj = form.save()
            log_action(user=request.user, action="update", obj=obj, details="Изменено оборудование")
            messages.success(request, "Оборудование обновлено.")
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
        try:
            obj_repr = str(obj)
            obj_id = str(obj.id)
            obj.delete()
            log_action(
                user=request.user,
                action="delete",
                entity_type="Equipment",
                entity_id=obj_id,
                entity_repr=obj_repr,
                details="Удалено оборудование",
            )
            messages.success(request, "Оборудование удалено.")
        except ProtectedError:
            messages.error(
                request,
                "Нельзя удалить: оборудование используется в мероприятиях. "
                "Лучше сделать 'архив' (скрыть из списка), чтобы история не ломалась."
            )
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
            obj = form.save()
            log_action(user=request.user, action="create", obj=obj, details="Создана категория")
            messages.success(request, "Категория добавлена.")
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

    obj = get_object_or_404(EquipmentCategory, id=category_id)

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save()
            log_action(user=request.user, action="update", obj=obj, details="Изменена категория")
            messages.success(request, "Категория обновлена.")
            return redirect("equipment_list_categories")
    else:
        form = CategoryForm(instance=obj)

    return render(request, "inventory/category_form.html", {
        "form": form,
        "title": "Редактировать категорию",
    })


@login_required
@login_required
def category_delete_view(request, category_id):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    obj = get_object_or_404(EquipmentCategory, id=category_id)
    equipment_count = Equipment.objects.filter(category=obj).count()

    if request.method == "POST":
        # Если в категории есть оборудование — удалять нельзя
        if equipment_count > 0:
            messages.error(
                request,
                f"Нельзя удалить категорию: в ней {equipment_count} шт. оборудования. Сначала перенесите или удалите предметы."
            )
            return redirect("equipment_list_categories")

        obj_repr = str(obj)
        obj_id = str(obj.id)

        try:
            obj.delete()
        except ProtectedError:
            messages.error(
                request,
                "Нельзя удалить категорию, потому что в ней есть оборудование. Сначала перенесите или удалите предметы из этой категории."
            )
            return redirect("equipment_list_categories")

        log_action(
            user=request.user,
            action="delete",
            entity_type="EquipmentCategory",
            message=f"Удалена категория: {obj_repr} (id={obj_id})",
        )
        messages.success(request, "Категория удалена.")
        return redirect("equipment_list_categories")

    return render(request, "inventory/category_confirm_delete.html", {
        "category": obj,
        "equipment_count": equipment_count,
    })
