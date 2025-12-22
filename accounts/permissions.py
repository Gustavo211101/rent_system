from django.contrib.auth.models import Group


# Основные названия групп (ролей)
ROLE_MANAGER = "Менеджер"
ROLE_SENIOR_ENGINEER = "Старший инженер"
ROLE_ENGINEER = "Инженер"

# --- Алиасы для совместимости со старым кодом ---
# Если где-то в проекте импортируют ROLE_SENIOR / ROLE_ADMIN / ROLE_VIEWER и т.п.
ROLE_SENIOR = ROLE_SENIOR_ENGINEER
ROLE_ADMIN = ROLE_MANAGER
ROLE_VIEWER = ROLE_ENGINEER
# ----------------------------------------------


def _has_group(user, group_name: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return user.groups.filter(name=group_name).exists()


def get_user_role_name(user) -> str:
    """
    Возвращает отображаемое имя роли (группы) для пользователя.
    Если у пользователя несколько групп — приоритет:
    Менеджер > Старший инженер > Инженер > первая группа > ''.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return ""

    if user.is_superuser:
        return "Суперадмин"

    if _has_group(user, ROLE_MANAGER):
        return ROLE_MANAGER
    if _has_group(user, ROLE_SENIOR_ENGINEER):
        return ROLE_SENIOR_ENGINEER
    if _has_group(user, ROLE_ENGINEER):
        return ROLE_ENGINEER

    first = user.groups.first()
    return first.name if first else ""


# -------------------------
# Права (основные)
# -------------------------

def user_can_manage_staff(user) -> bool:
    """Доступ к разделу "Персонал" (пользователи/роли). Только Менеджер/суперпользователь."""
    return bool(user and user.is_authenticated and (user.is_superuser or _has_group(user, ROLE_MANAGER)))


def user_can_manage_inventory(user) -> bool:
    """Может создавать/редактировать оборудование и категории. Только Менеджер/суперпользователь."""
    return bool(user and user.is_authenticated and (user.is_superuser or _has_group(user, ROLE_MANAGER)))


def user_can_edit_event_card(user) -> bool:
    """Может менять карточку мероприятия (даты/статус/клиент/локация). Только Менеджер/суперпользователь."""
    return bool(user and user.is_authenticated and (user.is_superuser or _has_group(user, ROLE_MANAGER)))


def user_can_edit_event_equipment(user) -> bool:
    """Может менять оборудование в мероприятии. Менеджер + Старший инженер + суперпользователь."""
    return bool(
        user and user.is_authenticated and (
            user.is_superuser
            or _has_group(user, ROLE_MANAGER)
            or _has_group(user, ROLE_SENIOR_ENGINEER)
        )
    )


def user_can_view(user) -> bool:
    """Просмотр (все авторизованные)."""
    return bool(user and user.is_authenticated)


# -------------------------
# Алиасы функций для обратной совместимости
# -------------------------

# Часто было: user_can_edit(request.user)
def user_can_edit(user) -> bool:
    return user_can_edit_event_card(user)


# Иногда встречалось: user_can_edit_equipment
def user_can_edit_equipment(user) -> bool:
    return user_can_edit_event_equipment(user)


# На всякий случай — если старый код импортирует такие имена:
def can_manage_staff(user) -> bool:
    return user_can_manage_staff(user)


def can_manage_inventory(user) -> bool:
    return user_can_manage_inventory(user)