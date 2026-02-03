
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from accounts.permissions import can_view_stock, can_edit_inventory
from .models import StockEquipmentType, StockEquipmentItem
from .warehouse_items_forms import StockEquipmentItemForm

def _forbidden():
    return HttpResponse("Недостаточно прав", status=403)

@login_required
def stock_item_list_view(request, type_id):
    if not can_view_stock(request.user):
        return _forbidden()
    etype = get_object_or_404(StockEquipmentType, pk=type_id)
    items = StockEquipmentItem.objects.filter(equipment_type=etype).order_by("inventory_number")
    return render(request, "inventory/warehouse/items_list.html", {"etype": etype, "items": items, "can_manage": can_edit_inventory(request.user)})

@login_required
def stock_item_add_view(request, type_id):
    if not can_edit_inventory(request.user):
        return _forbidden()
    etype = get_object_or_404(StockEquipmentType, pk=type_id)
    form = StockEquipmentItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.equipment_type = etype
        obj.save()
        return redirect("stock_item_list", type_id=etype.id)
    return render(request, "inventory/warehouse/item_form.html", {"form": form, "etype": etype})

@login_required
def stock_item_edit_view(request, item_id):
    if not can_edit_inventory(request.user):
        return _forbidden()
    obj = get_object_or_404(StockEquipmentItem, pk=item_id)
    form = StockEquipmentItemForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("stock_item_list", type_id=obj.equipment_type.id)
    return render(request, "inventory/warehouse/item_form.html", {"form": form, "etype": obj.equipment_type})

@login_required
def stock_item_delete_view(request, item_id):
    if not can_edit_inventory(request.user):
        return _forbidden()
    obj = get_object_or_404(StockEquipmentItem, pk=item_id)
    tid = obj.equipment_type.id
    obj.delete()
    return redirect("stock_item_list", type_id=tid)

@login_required
def stock_item_card_view(request, item_id):
    if not can_view_stock(request.user):
        return _forbidden()
    obj = get_object_or_404(StockEquipmentItem, pk=item_id)
    return render(request, "inventory/warehouse/item_card.html", {"item": obj})

@login_required
def stock_item_qr_view(request, item_id):
    # stub QR
    return HttpResponse("QR будет тут", content_type="text/plain")
