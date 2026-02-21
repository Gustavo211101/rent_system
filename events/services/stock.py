from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Iterable, Tuple

from django.db import IntegrityError, transaction
from django.utils import timezone

from events.models import Event, EventStockIssue, EventStockReservation
from inventory.models import StockEquipmentItem


@dataclass
class StockActionResult:
    ok: bool
    message: str = ""


def _pick_status_value(
    model_cls: type,
    candidates: Iterable[str],
    fallback: str,
    *,
    field_name: str = "status",
) -> str:
    """Resolve a status value in a robust way across codebase versions.

    Tries:
      1) class attributes (constants) by name
      2) Django TextChoices on the class (e.g. Status.EVENT)
      3) values from the model field choices by best-effort matching
      4) fallback string
    """
    # 1) direct constants
    for name in candidates:
        val = getattr(model_cls, name, None)
        if isinstance(val, str) and val:
            return val

    # 2) common TextChoices containers
    for container_name in ("Status", "Statuses", "STATUS", "STATUSES"):
        container = getattr(model_cls, container_name, None)
        if container is None:
            continue
        for name in candidates:
            v = getattr(container, name, None)
            # TextChoices members have .value
            if hasattr(v, "value"):
                vv = getattr(v, "value")
                if isinstance(vv, str) and vv:
                    return vv
            if isinstance(v, str) and v:
                return v

    # 3) try field choices (value, label)
    try:
        field = model_cls._meta.get_field(field_name)
        choices = list(getattr(field, "choices", []) or [])
    except Exception:
        choices = []

    # Attempt by matching candidate keywords in labels and values
    def norm(s: Any) -> str:
        return str(s).strip().lower()

    cand_norm = [norm(c) for c in candidates]
    # first: exact value match on candidate names (common when constants == values)
    for value, label in choices:
        if norm(value) in cand_norm:
            return value

    # second: label contains typical substrings
    label_hints = {
        "event": ("меропр", "ивент", "event", "выдан", "на объект", "на площад"),
        "storage": ("склад", "storage", "warehouse", "в наличии", "на складе"),
        "repair": ("ремонт", "repair", "service", "в ремонте"),
    }
    # Determine which group this is by candidates/fallback
    group = None
    all_tokens = " ".join(cand_norm + [norm(fallback)])
    if "repair" in all_tokens or "ремонт" in all_tokens:
        group = "repair"
    elif "storage" in all_tokens or "склад" in all_tokens or "stock" in all_tokens:
        group = "storage"
    else:
        group = "event"

    hints = label_hints.get(group, ())
    for value, label in choices:
        nl = norm(label)
        nv = norm(value)
        if any(h in nl for h in hints) or any(h in nv for h in hints):
            return value

    return fallback


def _status_on_event() -> str:
    return _pick_status_value(
        StockEquipmentItem,
        candidates=(
            "STATUS_ON_EVENT",
            "STATUS_IN_EVENT",
            "STATUS_EVENT",
            "STATUS_AT_EVENT",
            "ON_EVENT",
            "IN_EVENT",
            "EVENT",
        ),
        fallback="event",
    )


def _status_storage() -> str:
    return _pick_status_value(
        StockEquipmentItem,
        candidates=(
            "STATUS_STORAGE",
            "STATUS_IN_STOCK",
            "STATUS_STOCK",
            "STATUS_WAREHOUSE",
            "IN_STOCK",
            "STORAGE",
            "WAREHOUSE",
            "STOCK",
        ),
        fallback="storage",
    )


def _status_repair() -> str:
    return _pick_status_value(
        StockEquipmentItem,
        candidates=(
            "STATUS_REPAIR",
            "STATUS_IN_REPAIR",
            "IN_REPAIR",
            "REPAIR",
        ),
        fallback="repair",
    )


def _set_item_status(item: StockEquipmentItem, new_status: str, *, user, reason: str, meta: Optional[dict] = None) -> None:
    """Set item status using the project's existing API.

    Supports various signatures of StockEquipmentItem.set_status across versions:
      - set_status(new_status, user=..., reason=..., meta=...)
      - set_status(new_status, user=..., reason=...)
      - set_status(new_status)
    Fallback: direct assignment + save(update_fields=['status'])
    """
    if hasattr(item, "set_status") and callable(getattr(item, "set_status")):
        try:
            item.set_status(new_status, user=user, reason=reason, meta=meta)
            return
        except TypeError:
            try:
                item.set_status(new_status, user=user, reason=reason)
                return
            except TypeError:
                try:
                    item.set_status(new_status)
                    return
                except Exception:
                    pass

    item.status = new_status
    item.save(update_fields=["status"])


def _reservation_limit(event: Event, equipment_type) -> int:
    return (
        EventStockReservation.objects.filter(event=event, equipment_type=equipment_type)
        .values_list("quantity", flat=True)
        .first()
        or 0
    )


def _issued_count(event: Event, equipment_type) -> int:
    return EventStockIssue.objects.filter(event=event, item__equipment_type=equipment_type).count()


def _active_issue_for_item(item: StockEquipmentItem) -> Optional[EventStockIssue]:
    return (
        EventStockIssue.objects.select_related("event")
        .filter(item=item, returned_at__isnull=True)
        .order_by("-issued_at")
        .first()
    )


def issue_item_to_event(event: Event, item: StockEquipmentItem, user) -> StockActionResult:
    # basic checks
    if item.status == _status_repair():
        return StockActionResult(False, "Единица в ремонте — выдача невозможна.")

    # must have reservation for this type
    reserved_qty = _reservation_limit(event, item.equipment_type)
    if reserved_qty <= 0:
        return StockActionResult(False, "Для этого типа нет брони в мероприятии.")

    issued_qty = _issued_count(event, item.equipment_type)
    if issued_qty >= reserved_qty:
        return StockActionResult(False, "Лимит по брони уже выбран.")

    # already issued somewhere?
    active = _active_issue_for_item(item)
    if active is not None:
        if active.event_id == event.id:
            return StockActionResult(False, "Эта единица уже выдана на данное мероприятие.")
        return StockActionResult(False, "Эта единица уже выдана на другое мероприятие.")

    try:
        with transaction.atomic():
            EventStockIssue.objects.create(event=event, item=item, issued_at=timezone.now(), issued_by=user)
            _set_item_status(
                item,
                _status_on_event(),
                user=user,
                reason=f"Выдача на мероприятие #{event.id}",
                meta={"event_id": event.id, "action": "issue"},
            )
        return StockActionResult(True, "Выдано.")
    except IntegrityError:
        # race condition / constraint hit
        return StockActionResult(False, "Не удалось выдать: единица уже выдана или добавлена ранее (конфликт).")


def return_item_from_event(event: Event, item: StockEquipmentItem, user) -> StockActionResult:
    issue = (
        EventStockIssue.objects.filter(event=event, item=item, returned_at__isnull=True)
        .order_by("-issued_at")
        .first()
    )
    if issue is None:
        return StockActionResult(False, "Эта единица не числится выданной на данное мероприятие.")

    with transaction.atomic():
        issue.returned_at = timezone.now()
        issue.returned_by = user
        issue.save(update_fields=["returned_at", "returned_by"])

        # If item is currently in repair, don't overwrite.
        if item.status != _status_repair():
            _set_item_status(
                item,
                _status_storage(),
                user=user,
                reason=f"Возврат с мероприятия #{event.id}",
                meta={"event_id": event.id, "action": "return"},
            )
    return StockActionResult(True, "Возвращено.")


def can_cancel_event(event: Event) -> Tuple[bool, str]:
    if EventStockIssue.objects.filter(event=event).exists():
        return False, "Нельзя отменить мероприятие: уже были выдачи. Сначала верните оборудование."
    return True, ""


def can_close_event(event: Event) -> Tuple[bool, str]:
    if EventStockIssue.objects.filter(event=event, returned_at__isnull=True).exists():
        return False, "Нельзя закрыть мероприятие: есть невозвращённое оборудование."

    # ensure every reservation is fulfilled
    reservations = EventStockReservation.objects.filter(event=event).select_related("equipment_type")
    for r in reservations:
        issued = EventStockIssue.objects.filter(event=event, item__equipment_type=r.equipment_type).count()
        if issued < r.quantity:
            return False, f"Нельзя закрыть: по '{r.equipment_type}' выдано {issued} из {r.quantity}."
    return True, ""


def transfer_item_between_events(source_event: Event, target_event: Event, item: StockEquipmentItem, user) -> StockActionResult:
    # must be actively issued to source_event
    issue = (
        EventStockIssue.objects.filter(event=source_event, item=item, returned_at__isnull=True)
        .order_by("-issued_at")
        .first()
    )
    if issue is None:
        return StockActionResult(False, "Эта единица не выдана на исходное мероприятие (нечего переносить).")

    if item.status == _status_repair():
        return StockActionResult(False, "Единица в ремонте — перенос невозможен.")

    # target must have reservation capacity
    reserved_qty = _reservation_limit(target_event, item.equipment_type)
    if reserved_qty <= 0:
        return StockActionResult(False, "В целевом мероприятии нет брони по этому типу.")
    issued_qty = _issued_count(target_event, item.equipment_type)
    if issued_qty >= reserved_qty:
        return StockActionResult(False, "В целевом мероприятии лимит брони по этому типу уже выбран.")

    try:
        with transaction.atomic():
            # close old issue
            issue.returned_at = timezone.now()
            issue.returned_by = user
            issue.save(update_fields=["returned_at", "returned_by"])

            # create new issue in target
            EventStockIssue.objects.create(event=target_event, item=item, issued_at=timezone.now(), issued_by=user)

            # status remains "on event" conceptually; still write audit if supported
            _set_item_status(
                item,
                _status_on_event(),
                user=user,
                reason=f"Перевыдача: {source_event.id} → {target_event.id}",
                meta={"source_event_id": source_event.id, "target_event_id": target_event.id, "action": "transfer"},
            )
        return StockActionResult(True, "Перевыдано.")
    except IntegrityError:
        return StockActionResult(False, "Не удалось перевыдать (конфликт). Попробуйте ещё раз.")
