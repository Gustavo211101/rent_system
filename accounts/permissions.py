from __future__ import annotations


def _ok(user) -> bool:
    return bool(user and user.is_authenticated)


def is_super(user) -> bool:
    return bool(_ok(user) and getattr(user, "is_superuser", False))


def can_manage_staff(user) -> bool:
    return is_super(user) or (_ok(user) and user.has_perm("accounts.manage_staff"))


def can_edit_inventory(user) -> bool:
    return is_super(user) or (_ok(user) and user.has_perm("inventory.manage_inventory"))


def can_edit_event_card(user) -> bool:
    return is_super(user) or (_ok(user) and user.has_perm("events.edit_event_card"))


def can_edit_event_equipment(user) -> bool:
    return is_super(user) or (_ok(user) and user.has_perm("events.edit_event_equipment"))


# Алиасы под старый код
def user_can_manage_staff(user) -> bool:
    return can_manage_staff(user)


def user_can_edit_event_card(user) -> bool:
    return can_edit_event_card(user)


def user_can_edit_event_equipment(user) -> bool:
    return can_edit_event_equipment(user)


def user_can_edit_equipment(user) -> bool:
    return can_edit_inventory(user)


def user_can_edit(user) -> bool:
    return can_edit_event_card(user)
