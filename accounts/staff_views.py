from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Q, Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .permissions import (
    user_can_manage_staff,
    user_can_edit_event_card,
    user_can_edit_event_equipment,
    user_can_manage_inventory,
    ROLE_MANAGER,
    ROLE_SENIOR,
    ROLE_ENGINEER,
)
from .staff_forms import StaffUserCreateForm, StaffUserUpdateForm, StaffRoleForm

User = get_user_model()


def _staff_required(request):
    if not user_can_manage_staff(request.user):
        return False
    return True


def _ensure_default_roles():
    """
    Создаём 3 роли, если их нет.
    Права храним по логике приложения (не через django Permission),
    т.е. роль определяется названием Group.
    """
    for name in (ROLE_MANAGER, ROLE_SENIOR, ROLE_ENGINEER):
        Group.objects.get_or_create(name=name)


@login_required
def staff_users_view(request):
    if not _staff_required(request):
        return HttpResponseForbidden("Недостаточно прав")

    _ensure_default_roles()

    q = (request.GET.get("q") or "").strip()
    role_id = (request.GET.get("role") or "").strip()

    users = User.objects.all().order_by("username").prefetch_related("groups")

    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
        )

    if role_id:
        try:
            rid = int(role_id)
            users = users.filter(groups__id=rid)
        except ValueError:
            pass

    roles = Group.objects.all().order_by("name").annotate(user_count=Count("user"))

    return render(request, "accounts/staff_users.html", {
        "tab": "users",
        "users": users,
        "roles": roles,
        "q": q,
        "role_id": role_id,
    })


@login_required
def staff_user_create_view(request):
    if not _staff_required(request):
        return HttpResponseForbidden("Недостаточно прав")

    _ensure_default_roles()

    if request.method == "POST":
        form = StaffUserCreateForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("staff_users")
    else:
        form = StaffUserCreateForm()

    return render(request, "accounts/staff_user_form.html", {
        "tab": "users",
        "title": "Добавить пользователя",
        "form": form,
    })


@login_required
def staff_user_update_view(request, user_id: int):
    if not _staff_required(request):
        return HttpResponseForbidden("Недостаточно прав")

    user_obj = get_object_or_404(User, id=user_id)

    # суперпользователя редактируем только в админке (по твоему ТЗ)
    if user_obj.is_superuser:
        return HttpResponseForbidden("Суперпользователя редактируем только через админку")

    if request.method == "POST":
        form = StaffUserUpdateForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            return redirect("staff_users")
    else:
        form = StaffUserUpdateForm(instance=user_obj)

    return render(request, "accounts/staff_user_form.html", {
        "tab": "users",
        "title": "Редактировать пользователя",
        "form": form,
        "user_obj": user_obj,
    })


@login_required
def staff_user_delete_view(request, user_id: int):
    if not _staff_required(request):
        return HttpResponseForbidden("Недостаточно прав")

    user_obj = get_object_or_404(User, id=user_id)

    if user_obj.is_superuser:
        return HttpResponseForbidden("Суперпользователя удалять нельзя отсюда")

    if request.method == "POST":
        user_obj.delete()
        return redirect("staff_users")

    return render(request, "accounts/staff_confirm_delete.html", {
        "tab": "users",
        "title": "Удалить пользователя",
        "object_name": user_obj.username,
        "cancel_url": "staff_users",
    })


@login_required
def staff_roles_view(request):
    if not _staff_required(request):
        return HttpResponseForbidden("Недостаточно прав")

    _ensure_default_roles()

    roles = Group.objects.all().order_by("name").annotate(user_count=Count("user"))

    return render(request, "accounts/staff_roles.html", {
        "tab": "roles",
        "roles": roles,
    })


@login_required
def staff_role_create_view(request):
    if not _staff_required(request):
        return HttpResponseForbidden("Недостаточно прав")

    if request.method == "POST":
        form = StaffRoleForm(request.POST)
        if form.is_valid():
            group = form.save()
            return redirect("staff_roles")
    else:
        form = StaffRoleForm()

    return render(request, "accounts/staff_role_form.html", {
        "tab": "roles",
        "title": "Добавить роль",
        "form": form,
    })


@login_required
def staff_role_update_view(request, group_id: int):
    if not _staff_required(request):
        return HttpResponseForbidden("Недостаточно прав")

    group = get_object_or_404(Group, id=group_id)

    if request.method == "POST":
        form = StaffRoleForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            return redirect("staff_roles")
    else:
        form = StaffRoleForm(instance=group)

    return render(request, "accounts/staff_role_form.html", {
        "tab": "roles",
        "title": "Редактировать роль",
        "form": form,
        "group": group,
    })


@login_required
def staff_role_delete_view(request, group_id: int):
    if not _staff_required(request):
        return HttpResponseForbidden("Недостаточно прав")

    group = get_object_or_404(Group, id=group_id)

    if request.method == "POST":
        group.delete()
        return redirect("staff_roles")

    return render(request, "accounts/staff_confirm_delete.html", {
        "tab": "roles",
        "title": "Удалить роль",
        "object_name": group.name,
        "cancel_url": "staff_roles",
    })
