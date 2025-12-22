from .permissions import (
    is_manager,
    is_senior_engineer,
    is_engineer,
    can_manage_staff,
    can_edit_event_card,
    can_edit_event_equipment,
    can_edit_inventory,
)


def authz_flags(request):
    user = getattr(request, "user", None)
    return {
        "is_manager": is_manager(user),
        "is_senior_engineer": is_senior_engineer(user),
        "is_engineer": is_engineer(user),
        "can_manage_staff": can_manage_staff(user),
        "can_edit_event_card": can_edit_event_card(user),
        "can_edit_event_equipment": can_edit_event_equipment(user),
        "can_edit_inventory": can_edit_inventory(user),
    }