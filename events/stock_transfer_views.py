from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from events.models import Event, EventStockIssue
from inventory.models import StockEquipmentItem

from .services.stock import transfer_item_between_events


@login_required
def event_stock_transfer_view(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)

    result_message = None
    result_success = False

    target_event_id = request.POST.get("target_event_id") if request.method == "POST" else None

    if request.method == "POST":
        inventory_number = (request.POST.get("inventory_number") or "").strip()

        if not target_event_id:
            result_message = "Укажи ID целевого мероприятия."
        elif not inventory_number:
            result_message = "Сканируй инвентарник."
        else:
            target_event = get_object_or_404(Event, id=int(target_event_id))
            item = get_object_or_404(StockEquipmentItem, inventory_number=inventory_number)

            res = transfer_item_between_events(
                source_event=event,
                target_event=target_event,
                item=item,
                user=request.user,
            )
            result_message = res.message
            result_success = res.success

    open_issues = (
        EventStockIssue.objects.select_related("item", "item__equipment_type", "issued_by")
        .filter(event=event, returned_at__isnull=True)
        .order_by("-issued_at")
    )

    return render(
        request,
        "events/event_stock_transfer.html",
        {
            "event": event,
            "open_issues": list(open_issues),
            "result_message": result_message,
            "result_success": result_success,
            "target_event_id": target_event_id,
        },
    )
