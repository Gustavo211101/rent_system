from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .permissions import can_manage_staff
from .roles import ROLE_MANAGER, ROLE_SENIOR_ENGINEER, ROLE_ENGINEER

User = get_user_model()


# -----------------------
# helpers
# -----------------------
def _require_manager(request):
    if not can_manage_staff(request.user):
        return HttpResponseForbidden("Недостаточно прав")
    return None


def _user_primary_role_name(user) -> str:
    # Если пользователь состоит в нескольких группах — покажем первую по алфавиту
    groups = user.groups.order_by("name").values_list("name", flat=True)
    return groups[0] if groups else "—"


# -----------------------
# Personnel page
# -----------------------
@login_required
def personnel_view(request):
    deny = _require_manager(request)
    if deny:
        return deny

    query = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()

    users = User.objects.all().order_by("username")

    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )

    if role:
        users = users.filter(groups__name=role)

    roles = Group.objects.all().order_by("name")

    # подготовим отображаемую роль для таблицы
    user_rows = []
    for u in users:
        user_rows.append({
            "obj": u,
            "role_name": _user_primary_role_name(u),
        })

    return render(request, "accounts/personnel.html", {
        "tab": "users",
        "q": query,
        "role": role,
        "roles": roles,
        "user_rows": user_rows,
    })


@login_required
def user_create_view(request):
    deny = _require_manager(request)
    if deny:
        return deny

    roles = Group.objects.all().order_by("name")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = (request.POST.get("password") or "").strip()
        group_name = (request.POST.get("group") or "").strip()

        if not username or not password:
            messages.error(request, "Нужны username и пароль")
            return redirect("personnel")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Пользователь с таким username уже существует")
            return redirect("personnel")

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

        # суперпользователя не даём через UI
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_superuser"])

        user.groups.clear()
        if group_name:
            grp = Group.objects.filter(name=group_name).first()
            if grp:
                user.groups.add(grp)

        messages.success(request, "Пользователь создан")
        return redirect("personnel")

    return render(request, "accounts/user_form.html", {
        "title": "Добавить пользователя",
        "roles": roles,
        "user_obj": None,
    })


@login_required
def user_update_view(request, user_id: int):
    deny = _require_manager(request)
    if deny:
        return deny

    user_obj = get_object_or_404(User, id=user_id)
    roles = Group.objects.all().order_by("name")

    if request.method == "POST":
        user_obj.first_name = (request.POST.get("first_name") or "").strip()
        user_obj.last_name = (request.POST.get("last_name") or "").strip()
        user_obj.email = (request.POST.get("email") or "").strip()

        # роль (группа) — выбираем одну
        group_name = (request.POST.get("group") or "").strip()
        user_obj.groups.clear()
        if group_name:
            grp = Group.objects.filter(name=group_name).first()
            if grp:
                user_obj.groups.add(grp)

        # пароль можно сменить опционально
        password = (request.POST.get("password") or "").strip()
        if password:
            user_obj.set_password(password)

        # суперправа не трогаем
        user_obj.is_superuser = user_obj.is_superuser
        user_obj.is_staff = user_obj.is_staff

        user_obj.save()
        messages.success(request, "Пользователь обновлён")
        return redirect("personnel")

    return render(request, "accounts/user_form.html", {
        "title": "Редактировать пользователя",
        "roles": roles,
        "user_obj": user_obj,
        "current_role": _user_primary_role_name(user_obj),
    })


@login_required
def user_delete_view(request, user_id: int):
    deny = _require_manager(request)
    if deny:
        return deny

    user_obj = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        if user_obj.is_superuser:
            messages.error(request, "Суперпользователя нельзя удалить отсюда")
            return redirect("personnel")
        user_obj.delete()
        messages.success(request, "Пользователь удалён")
        return redirect("personnel")

    return render(request, "accounts/user_delete_confirm.html", {
        "user_obj": user_obj
    })


# -----------------------
# Roles (Groups) page
# -----------------------

def _apply_role_profile(group: Group, profile: str):
    """
    Настраиваем права группы набором чекбоксов.
    Мы не лезем в суперправа. Только группы.
    """
    group.permissions.clear()

    # Профили:
    # manager: всё (events + inventory + auth group/user управление НЕ через perms, а через UI)
    # senior: только оборудование в мероприятии (EventEquipment + EventRentedEquipment)
    # engineer: только просмотр (пусто)

    from django.contrib.auth.models import Permission

    def add_perm(app_label: str, model: str, codename_prefix: str):
        codename = f"{codename_prefix}_{model}"
        perm = Permission.objects.filter(content_type__app_label=app_label, codename=codename).first()
        if perm:
            group.permissions.add(perm)

    if profile == "manager":
        # events: Event, EventEquipment, EventRentedEquipment
        for prefix in ("add", "change", "delete", "view"):
            add_perm("events", "event", prefix)
            add_perm("events", "eventequipment", prefix)
            add_perm("events", "eventrentedequipment", prefix)

        # inventory: EquipmentCategory, Equipment
        for prefix in ("add", "change", "delete", "view"):
            add_perm("inventory", "equipmentcategory", prefix)
            add_perm("inventory", "equipment", prefix)

    elif profile == "senior":
        for prefix in ("add", "change", "delete", "view"):
            add_perm("events", "eventequipment", prefix)
            add_perm("events", "eventrentedequipment", prefix)
            add_perm("events", "event", "view")

    elif profile == "engineer":
        add_perm("events", "event", "view")
        add_perm("events", "eventequipment", "view")
        add_perm("events", "eventrentedequipment", "view")
        add_perm("inventory", "equipmentcategory", "view")
        add_perm("inventory", "equipment", "view")


@login_required
def roles_view(request):
    deny = _require_manager(request)
    if deny:
        return deny

    roles = Group.objects.all().order_by("name")

    return render(request, "accounts/personnel.html", {
        "tab": "roles",
        "roles": roles,
    })


@login_required
def role_create_view(request):
    deny = _require_manager(request)
    if deny:
        return deny

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        profile = (request.POST.get("profile") or "").strip()

        if not name:
            messages.error(request, "Название роли обязательно")
            return redirect("personnel_roles")

        if Group.objects.filter(name=name).exists():
            messages.error(request, "Такая роль уже существует")
            return redirect("personnel_roles")

        group = Group.objects.create(name=name)

        # если выбран профиль — применим
        if profile in ("manager", "senior", "engineer"):
            _apply_role_profile(group, profile)

        messages.success(request, "Роль создана")
        return redirect("personnel_roles")

    return render(request, "accounts/role_form.html", {
        "title": "Создать роль",
        "group_obj": None,
    })


@login_required
def role_update_view(request, group_id: int):
    deny = _require_manager(request)
    if deny:
        return deny

    group = get_object_or_404(Group, id=group_id)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        profile = (request.POST.get("profile") or "").strip()

        if not name:
            messages.error(request, "Название роли обязательно")
            return redirect("personnel_roles")

        # переименование
        if Group.objects.exclude(id=group.id).filter(name=name).exists():
            messages.error(request, "Роль с таким названием уже существует")
            return redirect("personnel_roles")

        group.name = name
        group.save(update_fields=["name"])

        # профиль прав
        if profile in ("manager", "senior", "engineer"):
            _apply_role_profile(group, profile)

        messages.success(request, "Роль обновлена")
        return redirect("personnel_roles")

    return render(request, "accounts/role_form.html", {
        "title": "Редактировать роль",
        "group_obj": group,
    })


@login_required
def role_delete_view(request, group_id: int):
    deny = _require_manager(request)
    if deny:
        return deny

    group = get_object_or_404(Group, id=group_id)

    if request.method == "POST":
        group.delete()
        messages.success(request, "Роль удалена")
        return redirect("personnel_roles")

    return render(request, "accounts/role_delete_confirm.html", {
        "group_obj": group
    })
