from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import can_edit_inventory
from audit.utils import log_action
from .models import Equipment, EquipmentCategory, EquipmentRepair


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


# ---------- Repairs (ремонт) ----------

class EquipmentRepairForm(forms.ModelForm):
    class Meta:
        model = EquipmentRepair
        fields = ["equipment", "quantity", "start_date", "note"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.TextInput(),
        }


@login_required
def repair_list_view(request):
    # Доступ только менеджеру/суперадмину
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    status = (request.GET.get("status") or "active").strip()
    if status not in {"active", "closed", "all"}:
        status = "active"

    qs = (
        EquipmentRepair.objects
        .select_related("equipment", "equipment__category")
        .order_by("-created_at", "-id")
    )

    if status == "active":
        qs = qs.filter(status=EquipmentRepair.STATUS_IN_REPAIR)
    elif status == "closed":
        qs = qs.filter(status=EquipmentRepair.STATUS_RETURNED)

    return render(request, "inventory/repair_list.html", {
        "repairs": qs,
        "status": status,
        "can_manage": True,
    })


@login_required
def repair_create_view(request):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = EquipmentRepairForm(request.POST)
        if form.is_valid():
            repair = form.save(commit=False)

            # защита: нельзя отправить в ремонт больше, чем всего есть
            if repair.quantity <= 0:
                messages.error(request, "Количество должно быть больше 0.")
                return render(request, "inventory/repair_form.html", {"form": form, "title": "В ремонт"})

            if repair.quantity > repair.equipment.quantity_total:
                messages.error(request, "Количество в ремонте не может превышать общее количество.")
                return render(request, "inventory/repair_form.html", {"form": form, "title": "В ремонт"})

            repair.status = EquipmentRepair.STATUS_IN_REPAIR
            repair.end_date = None
            repair.save()

            log_action(user=request.user, action="create", obj=repair, details="Оборудование отправлено в ремонт")
            messages.success(request, "Добавлено в ремонт.")
            return redirect("repair_list")
    else:
        form = EquipmentRepairForm()

    return render(request, "inventory/repair_form.html", {"form": form, "title": "В ремонт"})


@login_required
def repair_close_view(request, repair_id):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    repair = get_object_or_404(EquipmentRepair, id=repair_id)

    if request.method == "POST":
        repair.status = EquipmentRepair.STATUS_RETURNED
        repair.end_date = timezone.localdate()
        repair.save(update_fields=["status", "end_date"])

        log_action(user=request.user, action="update", obj=repair, details="Возврат из ремонта")
        messages.success(request, "Возвращено из ремонта.")
        return redirect("repair_list")

    # GET: подтверждение (простая)
    return render(request, "inventory/repair_close_confirm.html", {"repair": repair})


@login_required
def repair_delete_view(request, repair_id):
    if not can_edit_inventory(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    repair = get_object_or_404(EquipmentRepair, id=repair_id)

    if request.method == "POST":
        log_action(user=request.user, action="delete", obj=repair, details="Удалена запись ремонта")
        repair.delete()
        messages.success(request, "Запись ремонта удалена.")
        return redirect("repair_list")

    return render(request, "inventory/repair_delete_confirm.html", {"repair": repair})
