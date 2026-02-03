from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import can_edit_inventory, can_view_stock

from .models import StockEquipmentType, StockEquipmentItem
from .warehouse_items_forms import StockEquipmentItemForm


def _forbidden():
    return HttpResponseForbidden("Недостаточно прав")


def _can_manage(user) -> bool:
    return can_edit_inventory(user)


@login_required
def stock_items_list_view(request, type_id: int):
    if not can_view_stock(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    items = StockEquipmentItem.objects.filter(equipment_type=eq_type).order_by("inventory_number", "id")

    return render(
        request,
        "inventory/warehouse/items_list.html",
        {
            "eq_type": eq_type,
            "items": items,
            "can_manage": _can_manage(request.user),
        },
    )


@login_required
def stock_item_add_view(request, type_id: int):
    if not can_view_stock(request.user):
        return _forbidden()
    if not _can_manage(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    form = StockEquipmentItemForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if form.is_valid():
            obj: StockEquipmentItem = form.save(commit=False)
            obj.equipment_type = eq_type
            obj.save()
            messages.success(request, "Единица оборудования добавлена.")
            return redirect("stock_items_list", type_id=eq_type.id)
        messages.error(request, "Исправьте ошибки в форме.")

    return render(
        request,
        "inventory/warehouse/item_form.html",
        {"form": form, "eq_type": eq_type, "mode": "add"},
    )


@login_required
def stock_item_edit_view(request, type_id: int, item_id: int):
    if not can_view_stock(request.user):
        return _forbidden()
    if not _can_manage(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    item = get_object_or_404(StockEquipmentItem, pk=item_id, equipment_type=eq_type)

    form = StockEquipmentItemForm(request.POST or None, request.FILES or None, instance=item)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Единица оборудования обновлена.")
            return redirect("stock_items_list", type_id=eq_type.id)
        messages.error(request, "Исправьте ошибки в форме.")

    return render(
        request,
        "inventory/warehouse/item_form.html",
        {"form": form, "eq_type": eq_type, "item": item, "mode": "edit"},
    )


@login_required
def stock_item_delete_view(request, type_id: int, item_id: int):
    if not can_view_stock(request.user):
        return _forbidden()
    if not _can_manage(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    item = get_object_or_404(StockEquipmentItem, pk=item_id, equipment_type=eq_type)

    if request.method == "POST":
        item.delete()
        messages.success(request, "Единица оборудования удалена.")
    return redirect("stock_items_list", type_id=eq_type.id)


@login_required
def stock_item_card_view(request, type_id: int, item_id: int):
    if not can_view_stock(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    item = get_object_or_404(StockEquipmentItem, pk=item_id, equipment_type=eq_type)

    return render(
        request,
        "inventory/warehouse/item_card.html",
        {"eq_type": eq_type, "item": item},
    )

@login_required
def stock_item_qr_view(request, type_id: int, item_id: int):
    """Страница с QR-кодом для печати наклейки.

    QR кодирует инвентарный номер (inventory_number).
    """
    if not can_view_stock(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    item = get_object_or_404(StockEquipmentItem, pk=item_id, equipment_type=eq_type)

    # Строка, которую кодируем в QR. Можно расширить позже (URL, json и т.п.)
    qr_data = item.inventory_number

    return render(
        request,
        "inventory/warehouse/item_qr.html",
        {
            "eq_type": eq_type,
            "item": item,
            "qr_data": qr_data,
        },
    )
