from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import can_edit_inventory, can_view_stock

from .models import StockCategory, StockSubcategory, StockEquipmentType, StockEquipmentItem
from .warehouse_types_forms import StockEquipmentTypeForm


def _forbidden():
    return HttpResponseForbidden("Недостаточно прав")


def _can_manage(user) -> bool:
    # Кладовщик (и суперюзер) — может. Менеджер — только просмотр.
    return can_edit_inventory(user)


@login_required
def stock_type_list_view(request):
    """Главная страница склада: список типов оборудования (без единиц)."""
    if not can_view_stock(request.user):
        return _forbidden()

    category_id = request.GET.get("category") or ""
    subcategory_id = request.GET.get("subcategory") or ""
    q = (request.GET.get("q") or "").strip()

    types = StockEquipmentType.objects.select_related("category", "subcategory").all()

    if category_id.isdigit():
        types = types.filter(category_id=int(category_id))
    if subcategory_id.isdigit():
        types = types.filter(subcategory_id=int(subcategory_id))
    if q:
        types = types.filter(name__icontains=q)

    # Счётчики по единицам (если единицы ещё не заведены — будет 0)
    item_counts = (
        StockEquipmentItem.objects
        .values("equipment_type_id")
        .annotate(
            total=Count("id"),
            on_stock=Count("id", filter=Q(status=StockEquipmentItem.STATUS_STORAGE)),
            in_repair=Count("id", filter=Q(status=StockEquipmentItem.STATUS_REPAIR)),
            on_event=Count("id", filter=Q(status=StockEquipmentItem.STATUS_EVENT)),
        )
    )
    counts_map = {row["equipment_type_id"]: row for row in item_counts}

    categories = StockCategory.objects.all().order_by("name")
    subcategories = StockSubcategory.objects.all().order_by("name")
    if category_id.isdigit():
        subcategories = subcategories.filter(category_id=int(category_id))

    return render(
        request,
        "inventory/warehouse/types_list.html",
        {
            "types": types.order_by("name"),
            "categories": categories,
            "subcategories": subcategories,
            "category_id": category_id,
            "subcategory_id": subcategory_id,
            "q": q,
            "counts_map": counts_map,
            "can_manage": _can_manage(request.user),
        },
    )


@login_required
def stock_type_add_view(request):
    if not can_view_stock(request.user):
        return _forbidden()
    if not _can_manage(request.user):
        return _forbidden()

    form = StockEquipmentTypeForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Тип оборудования добавлен.")
            return redirect("stock_type_list")
        messages.error(request, "Исправьте ошибки в форме.")

    return render(request, "inventory/warehouse/type_form.html", {"form": form, "mode": "add"})


@login_required
def stock_type_edit_view(request, type_id: int):
    if not can_view_stock(request.user):
        return _forbidden()
    if not _can_manage(request.user):
        return _forbidden()

    obj = get_object_or_404(StockEquipmentType, pk=type_id)
    form = StockEquipmentTypeForm(request.POST or None, instance=obj)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Тип оборудования обновлён.")
            return redirect("stock_type_list")
        messages.error(request, "Исправьте ошибки в форме.")

    return render(
        request,
        "inventory/warehouse/type_form.html",
        {"form": form, "mode": "edit", "obj": obj},
    )


@login_required
def stock_type_delete_view(request, type_id: int):
    if not can_view_stock(request.user):
        return _forbidden()
    if not _can_manage(request.user):
        return _forbidden()

    obj = get_object_or_404(StockEquipmentType, pk=type_id)

    # Нельзя удалить тип, если есть единицы
    if StockEquipmentItem.objects.filter(equipment_type=obj).exists():
        messages.error(request, "Нельзя удалить тип: есть заведённые единицы оборудования.")
        return redirect("stock_type_list")

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Тип оборудования удалён.")
        return redirect("stock_type_list")

    # Если кто-то открыл GET — просто вернём на список
    return redirect("stock_type_list")