from __future__ import annotations

from .permissions import (
    can_manage_staff,
    can_edit_event_card,
    can_edit_event_equipment,
    can_edit_inventory,
    can_view_stock,
)


def authz_flags(request):
    user = getattr(request, "user", None)
    return {
        # кто видит "Персонал" и "Журнал"
        "can_manage_staff": can_manage_staff(user),

        # кто может создавать/редактировать карточки мероприятий/менять статусы
        "can_edit_event_card": can_edit_event_card(user),

        # кто может менять оборудование/аренду внутри мероприятия
        "can_edit_event_equipment": can_edit_event_equipment(user),

        # кто может CRUD инвентаря
        "can_edit_inventory": can_edit_inventory(user),

        # кто видит склад (кладовщик + менеджер)
        "can_view_stock": can_view_stock(user),
    }
