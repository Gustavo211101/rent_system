from __future__ import annotations

from django.utils import timezone

from .models import AuditLog


def _model_field_names(model) -> set[str]:
    return {f.name for f in model._meta.get_fields()}


def log_action(
    *,
    user=None,
    action: str = "",
    obj=None,
    entity_type: str | None = None,
    message: str | None = None,
    details: str | None = None,
):
    """
    Универсальный логгер, который НЕ ломается из-за разных названий полей в AuditLog.

    Поддерживает:
      - message="..."
      - details="..." (алиас к message)
    """

    # details -> message (если message не задан)
    if message is None:
        message = details or ""
    if message is None:
        message = ""

    # entity_type по умолчанию из объекта
    if entity_type is None:
        entity_type = obj.__class__.__name__ if obj is not None else ""

    object_id = getattr(obj, "pk", None) if obj is not None else None
    object_repr = str(obj) if obj is not None else ""

    # реальные поля модели
    fields = _model_field_names(AuditLog)

    data = {}

    # created_at (разные имена)
    for name in ("created_at", "created", "timestamp", "time"):
        if name in fields:
            data[name] = timezone.now()
            break

    # user (разные имена)
    if user is not None and getattr(user, "is_authenticated", False):
        for name in ("user", "actor", "created_by", "author"):
            if name in fields:
                data[name] = user
                break

    # action (разные имена)
    for name in ("action", "verb", "event", "operation"):
        if name in fields:
            data[name] = action
            break

    # entity_type (разные имена)
    for name in ("entity_type", "entity", "model", "content_type"):
        if name in fields:
            data[name] = entity_type
            break

    # object_id (разные имена)
    if object_id is not None:
        for name in ("object_id", "obj_id", "entity_id", "target_id"):
            if name in fields:
                data[name] = object_id
                break

    # object_repr (разные имена)
    if object_repr:
        for name in ("object_repr", "obj_repr", "target_repr", "title"):
            if name in fields:
                data[name] = object_repr
                break

    # message/details/text (разные имена)
    if message:
        for name in ("message", "details", "text", "description", "note"):
            if name in fields:
                data[name] = message
                break

    # Создаём запись (только по тем полям, которые существуют)
    AuditLog.objects.create(**data)
