from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from events.models import Event, EventStockIssue
from inventory.models import StockEquipmentItem

from .services.stock import transfer_item_between_events


ACTIVE_STATUSES = (Event.STATUS_DRAFT, Event.STATUS_CONFIRMED)


@login_required
def event_stock_transfer_view(request, event_id: int):
    event = get_object_or_404(Event, id=event_id)

    result_message = None
    result_success = False

    # Target selection
    target_event_id = (request.POST.get("target_event_id") or "").strip() if request.method == "POST" else (request.GET.get("target") or "").strip()
    q = (request.GET.get("q") or "").strip()

    if request.method == "POST":
        inventory_number = ((request.POST.get("code") or request.POST.get("inventory_number")) or "").strip()

        if not target_event_id:
            result_message = "Выбери целевое мероприятие."
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
            result_success = getattr(res, "success", None)
            if result_success is None:
                result_success = getattr(res, "ok", False)

    # Search + list for selecting target event
    base_qs = (
        Event.objects
        .filter(is_deleted=False, status__in=ACTIVE_STATUSES)
        .exclude(id=event.id)
        .order_by("-start_date", "-id")
    )

    if q:
        cond = Q(name__icontains=q) | Q(client__icontains=q) | Q(location__icontains=q)
        if q.isdigit():
            cond = cond | Q(id=int(q))
        target_events = list(base_qs.filter(cond)[:30])
    else:
        # default: show a short list of recent/upcoming active events
        target_events = list(base_qs[:15])

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
            "q": q,
            "target_events": target_events,
        },
    )
