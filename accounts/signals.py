from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from .permissions import ROLE_NAMES, ROLE_MANAGER, ROLE_SENIOR_ENGINEER, ROLE_ENGINEER


def _perm(app_label: str, model: str, action: str) -> str:
    # action: add/change/delete/view
    return f"{action}_{model}"


def ensure_default_roles(sender, **kwargs):
    """
    Создаём группы-ролей, если их нет, и задаём "стартовые" права.

    Важно:
    - Эти права можно потом менять в интерфейсе "Персонал -> Роли".
    - superuser права не трогаем (они отдельно).
    """

    # 1) гарантируем наличие групп
    groups = {}
    for name in ROLE_NAMES:
        g, _ = Group.objects.get_or_create(name=name)
        groups[name] = g

    # 2) собираем permissions, которые нам нужны
    wanted = []

    # accounts.User (кастомный)
    # Имя модели в permissions обычно "user" (lowercase), app_label "accounts"
    # Если вдруг у тебя другое имя модели — это всё равно корректно подхватится через ContentType ниже.
    # Мы берём по codename, так надёжнее.
    user_ct = ContentType.objects.filter(app_label="accounts", model="user").first()

    # auth.Group
    group_ct = ContentType.objects.filter(app_label="auth", model="group").first()

    # events.Event
    event_ct = ContentType.objects.filter(app_label="events", model="event").first()
    ee_ct = ContentType.objects.filter(app_label="events", model="eventequipment").first()
    re_ct = ContentType.objects.filter(app_label="events", model="eventrentedequipment").first()

    # inventory models
    eq_ct = ContentType.objects.filter(app_label="inventory", model="equipment").first()
    cat_ct = ContentType.objects.filter(app_label="inventory", model="equipmentcategory").first()

    def perms_for_ct(ct, model_codename: str, actions=("view", "add", "change", "delete")):
        if not ct:
            return []
        codenames = [_perm(ct.app_label, model_codename, a) for a in actions]
        return list(Permission.objects.filter(content_type=ct, codename__in=codenames))

    # Собираем
    if user_ct:
        wanted += perms_for_ct(user_ct, "user", ("view", "add", "change", "delete"))
    if group_ct:
        wanted += perms_for_ct(group_ct, "group", ("view", "add", "change", "delete"))

    if event_ct:
        wanted += perms_for_ct(event_ct, "event", ("view", "add", "change", "delete"))
    if ee_ct:
        wanted += perms_for_ct(ee_ct, "eventequipment", ("view", "add", "change", "delete"))
    if re_ct:
        wanted += perms_for_ct(re_ct, "eventrentedequipment", ("view", "add", "change", "delete"))

    if eq_ct:
        wanted += perms_for_ct(eq_ct, "equipment", ("view", "add", "change", "delete"))
    if cat_ct:
        wanted += perms_for_ct(cat_ct, "equipmentcategory", ("view", "add", "change", "delete"))

    # 3) Стартовые права по твоему ТЗ
    # Менеджер: пользователи/роли/мероприятия/оборудование — всё.
    manager_perms = set(wanted)

    # Старший инженер: может смотреть события и работать с оборудованием в событии.
    senior_perms = set()
    if event_ct:
        senior_perms.update(perms_for_ct(event_ct, "event", ("view",)))
    if ee_ct:
        senior_perms.update(perms_for_ct(ee_ct, "eventequipment", ("view", "add", "change", "delete")))
    if re_ct:
        senior_perms.update(perms_for_ct(re_ct, "eventrentedequipment", ("view", "add", "change", "delete")))
    if eq_ct:
        senior_perms.update(perms_for_ct(eq_ct, "equipment", ("view",)))
    if cat_ct:
        senior_perms.update(perms_for_ct(cat_ct, "equipmentcategory", ("view",)))

    # Инженер: только просмотр
    engineer_perms = set()
    if event_ct:
        engineer_perms.update(perms_for_ct(event_ct, "event", ("view",)))
    if ee_ct:
        engineer_perms.update(perms_for_ct(ee_ct, "eventequipment", ("view",)))
    if re_ct:
        engineer_perms.update(perms_for_ct(re_ct, "eventrentedequipment", ("view",)))
    if eq_ct:
        engineer_perms.update(perms_for_ct(eq_ct, "equipment", ("view",)))
    if cat_ct:
        engineer_perms.update(perms_for_ct(cat_ct, "equipmentcategory", ("view",)))

    # 4) Применяем (если ты хочешь, чтобы это не перетирало ручные настройки — скажи, поменяем стратегию)
    groups[ROLE_MANAGER].permissions.set(manager_perms)
    groups[ROLE_SENIOR_ENGINEER].permissions.set(senior_perms)
    groups[ROLE_ENGINEER].permissions.set(engineer_perms)
