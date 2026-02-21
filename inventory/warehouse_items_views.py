from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.permissions import can_edit_inventory, can_view_stock
from audit.models import AuditLog

from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics import renderSVG

from .models import StockEquipmentType, StockEquipmentItem, StockRepair
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

    open_repair = (
        StockRepair.objects.filter(equipment_item=item, closed_at__isnull=True)
        .order_by("-opened_at", "-id")
        .first()
    )

    # ✅ История ремонтов (все, включая закрытые)
    repairs = (
        StockRepair.objects.filter(equipment_item=item)
        .select_related("opened_by", "closed_by")
        .order_by("-opened_at", "-id")
    )

    movements = (
        AuditLog.objects.filter(entity_type="StockEquipmentItem", entity_id=str(item.id))
        .select_related("actor")
        .order_by("-created_at", "-id")[:30]
    )

    return render(
        request,
        "inventory/warehouse/item_card.html",
        {
            "eq_type": eq_type,
            "item": item,
            "can_manage": _can_manage(request.user),
            "open_repair": open_repair,
            "repairs": repairs,
            "movements": movements,
        },
    )


@login_required
def stock_repair_detail_view(request, repair_id: int):
    """Карточка ремонта (чтобы читать заметки крупнее)."""
    if not can_view_stock(request.user):
        return _forbidden()

    repair = (
        StockRepair.objects.select_related(
            "equipment_item",
            "equipment_item__equipment_type",
            "opened_by",
            "closed_by",
        )
        .filter(pk=repair_id)
        .first()
    )
    if not repair:
        return HttpResponse("Ремонт не найден", status=404)

    eq_type = repair.equipment_item.equipment_type
    item = repair.equipment_item

    return render(
        request,
        "inventory/warehouse/repair_detail.html",
        {
            "repair": repair,
            "eq_type": eq_type,
            "item": item,
            "can_manage": _can_manage(request.user),
        },
    )


@login_required
def stock_item_qr_view(request, type_id: int, item_id: int):
    """
    Страница со штрихкодом (вместо QR).
    Исторически URL назван qr, но по ТЗ нужен BARCODE.
    Кодируем ТОЛЬКО цифровой инвентарник.
    """
    if not can_view_stock(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    item = get_object_or_404(StockEquipmentItem, pk=item_id, equipment_type=eq_type)

    return render(
        request,
        "inventory/warehouse/item_qr.html",
        {"eq_type": eq_type, "item": item},
    )


@login_required
def stock_item_barcode_svg_view(request, type_id: int, item_id: int):
    """Возвращает SVG со штрихкодом Code128."""
    if not can_view_stock(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    item = get_object_or_404(StockEquipmentItem, pk=item_id, equipment_type=eq_type)

    value = (item.inventory_number or "").strip()
    digits_only = "".join(ch for ch in value if ch.isdigit())
    if not digits_only:
        return HttpResponse("", content_type="image/svg+xml")

    drawing = createBarcodeDrawing(
        "Code128",
        value=digits_only,
        humanReadable=True,
        barHeight=32,
        quiet=False,
    )
    svg = renderSVG.drawToString(drawing)
    return HttpResponse(svg, content_type="image/svg+xml")


@login_required
def stock_item_label_print_view(request, type_id: int, item_id: int):
    """Страница печати этикетки (HTML)."""
    if not can_view_stock(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    item = get_object_or_404(StockEquipmentItem, pk=item_id, equipment_type=eq_type)

    return render(request, "inventory/warehouse/label_print.html", {"eq_type": eq_type, "item": item})


@login_required
@require_http_methods(["GET", "POST"])
def stock_item_open_repair_view(request, type_id: int, item_id: int):
    """Перевод единицы в ремонт с обязательной заметкой."""
    if not can_view_stock(request.user):
        return _forbidden()
    if not _can_manage(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    item = get_object_or_404(StockEquipmentItem, pk=item_id, equipment_type=eq_type)

    open_repair = (
        StockRepair.objects.filter(equipment_item=item, closed_at__isnull=True)
        .order_by("-opened_at", "-id")
        .first()
    )
    if open_repair:
        messages.info(request, "Эта единица уже находится в ремонте.")
        return redirect("stock_item_card", type_id=eq_type.id, item_id=item.id)

    if request.method == "POST":
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(request, "Укажите причину/заметку для ремонта.")
        else:
            StockRepair.objects.create(equipment_item=item, reason=reason, opened_by=request.user)
            item.set_status(
                StockEquipmentItem.STATUS_REPAIR,
                actor=request.user,
                reason=f"Отправлено в ремонт: {reason}",
            )
            messages.success(request, "Единица отправлена в ремонт.")
            return redirect("stock_item_card", type_id=eq_type.id, item_id=item.id)

    return render(request, "inventory/warehouse/repair_open_form.html", {"eq_type": eq_type, "item": item})


@login_required
@require_http_methods(["GET", "POST"])
def stock_item_close_repair_view(request, type_id: int, item_id: int):
    """Возврат из ремонта на склад с обязательной заметкой."""
    if not can_view_stock(request.user):
        return _forbidden()
    if not _can_manage(request.user):
        return _forbidden()

    eq_type = get_object_or_404(StockEquipmentType, pk=type_id)
    item = get_object_or_404(StockEquipmentItem, pk=item_id, equipment_type=eq_type)
    repair = get_object_or_404(StockRepair, equipment_item=item, closed_at__isnull=True)

    if request.method == "POST":
        note = (request.POST.get("close_note") or "").strip()
        if not note:
            messages.error(request, "Укажите заметку о результате ремонта/возврате.")
        else:
            repair.close_note = note
            repair.closed_at = timezone.now()
            repair.closed_by = request.user
            repair.save(update_fields=["close_note", "closed_at", "closed_by"])

            item.set_status(
                StockEquipmentItem.STATUS_STORAGE,
                actor=request.user,
                reason=f"Возврат из ремонта: {note}",
            )
            messages.success(request, "Единица возвращена на склад.")
            return redirect("stock_item_card", type_id=eq_type.id, item_id=item.id)

    return render(request, "inventory/warehouse/repair_close_form.html", {"eq_type": eq_type, "item": item, "repair": repair})