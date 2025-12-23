from __future__ import annotations

from typing import Optional, Any
from django.utils import timezone

from .models import AuditLog


def _safe_str(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return "<unprintable>"


def log_action(
    *,
    user,
    action: str,
    obj: Optional[Any] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    message: str = "",
) -> AuditLog:
    """
    action: create | update | delete
    """

    if obj is not None:
        if entity_type is None:
            entity_type = obj.__class__.__name__   # <-- ВАЖНО
        if entity_id is None:
            entity_id = getattr(obj, "pk", None)

    return AuditLog.objects.create(
        created_at=timezone.now(),
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        entity_type=entity_type or "",
        entity_id=entity_id,
        message=message,
        object_repr=_safe_str(obj) if obj else "",
    )
