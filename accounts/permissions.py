from __future__ import annotations

ROLE_MANAGER = "Менеджер"
ROLE_SENIOR = "Старший инженер"
ROLE_ENGINEER = "Инженер"


def _in_group(user, group_name: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()


def is_super(user) -> bool:
    return bool(user and user.is_authenticated and getattr(user, "is_superuser", False))


def is_manager(user) -> bool:
    return is_super(user) or _in_group(user, ROLE_MANAGER)


def is_senior_engineer(user) -> bool:
    return is_super(user) or _in_group(user, ROLE_SENIOR)


def is_engineer(user) -> bool:
    return is_super(user) or _in_group(user, ROLE_ENGINEER)


# === ПРАВА по ТЗ ===

def can_manage_staff(user) -> bool:
    # Персонал/роли — только менеджер и суперадмин
    return is_manager(user)


def can_edit_event_card(user) -> bool:
    # Карточка мероприятия + статус + даты — только менеджер и суперадмин
    return is_manager(user)


def can_edit_event_equipment(user) -> bool:
    # Оборудование/аренда внутри мероприятия — менеджер + старший инженер + суперадмин
    return is_manager(user) or is_senior_engineer(user)


def can_edit_inventory(user) -> bool:
    # Инвентарь (CRUD) — только менеджер и суперадмин
    return is_manager(user)


# === Алиасы, чтобы не падали старые импорты/вызовы ===

def user_can_manage_staff(user) -> bool:
    return can_manage_staff(user)


def user_can_edit_event_card(user) -> bool:
    return can_edit_event_card(user)


def user_can_edit_event_equipment(user) -> bool:
    return can_edit_event_equipment(user)


def user_can_edit_equipment(user) -> bool:
    return can_edit_inventory(user)


def user_can_edit(user) -> bool:
    # старое "can_edit" трактуем как "можно править карточку"
    return can_edit_event_card(user)