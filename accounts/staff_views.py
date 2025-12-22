from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .permissions import can_manage_staff


def _forbidden():
    return HttpResponseForbidden("Недостаточно прав")


@login_required
def staff_users_view(request):
    if not can_manage_staff(request.user):
        return _forbidden()

    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()  # Group.id

    users = User.objects.all().order_by("username")

    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        )

    if role.isdigit():
        users = users.filter(groups__id=int(role))

    roles = Group.objects.all().order_by("name")

    return render(request, "accounts/staff_users.html", {
        "users": users,
        "roles": roles,
        "q": q,
        "role": role,
        "tab": "users",
    })


@login_required
def staff_user_add_view(request):
    if not can_manage_staff(request.user):
        return _forbidden()

    roles = Group.objects.all().order_by("name")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = (request.POST.get("password") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        role_id = (request.POST.get("role_id") or "").strip()

        if not username or not password:
            messages.error(request, "Нужны username и пароль.")
            return render(request, "accounts/staff_user_form.html", {"roles": roles, "tab": "users"})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Пользователь с таким username уже существует.")
            return render(request, "accounts/staff_user_form.html", {"roles": roles, "tab": "users"})

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

        # роль (одна “основная”)
        user.groups.clear()
        if role_id.isdigit():
            grp = Group.objects.filter(id=int(role_id)).first()
            if grp:
                user.groups.add(grp)

        messages.success(request, "Пользователь создан.")
        return redirect("personnel")

    return render(request, "accounts/staff_user_form.html", {
        "roles": roles,
        "tab": "users",
    })


@login_required
def staff_user_edit_view(request, user_id):
    if not can_manage_staff(request.user):
        return _forbidden()

    user_obj = get_object_or_404(User, id=user_id)
    roles = Group.objects.all().order_by("name")

    if request.method == "POST":
        user_obj.first_name = (request.POST.get("first_name") or "").strip()
        user_obj.last_name = (request.POST.get("last_name") or "").strip()
        user_obj.email = (request.POST.get("email") or "").strip()

        # смена пароля (опционально)
        new_password = (request.POST.get("password") or "").strip()
        if new_password:
            user_obj.set_password(new_password)

        # роль (одна “основная”)
        role_id = (request.POST.get("role_id") or "").strip()
        user_obj.groups.clear()
        if role_id.isdigit():
            grp = Group.objects.filter(id=int(role_id)).first()
            if grp:
                user_obj.groups.add(grp)

        # суперпользователя тут НЕ даём назначать — только через админку
        user_obj.save()
        messages.success(request, "Пользователь обновлён.")
        return redirect("personnel")

    current_role = user_obj.groups.first()
    return render(request, "accounts/staff_user_form.html", {
        "user_obj": user_obj,
        "roles": roles,
        "current_role": current_role,
        "tab": "users",
    })


@login_required
def staff_user_delete_view(request, user_id):
    if not can_manage_staff(request.user):
        return _forbidden()

    user_obj = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        if user_obj.id == request.user.id:
            messages.error(request, "Нельзя удалить самого себя.")
            return redirect("personnel")
        user_obj.delete()
        messages.success(request, "Пользователь удалён.")
        return redirect("personnel")

    return render(request, "accounts/staff_user_confirm_delete.html", {
        "user_obj": user_obj,
        "tab": "users",
    })


@login_required
def staff_roles_view(request):
    if not can_manage_staff(request.user):
        return _forbidden()

    roles = Group.objects.all().order_by("name")
    return render(request, "accounts/staff_roles.html", {
        "roles": roles,
        "tab": "roles",
    })


@login_required
def staff_role_add_view(request):
    if not can_manage_staff(request.user):
        return _forbidden()

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Название роли обязательно.")
            return render(request, "accounts/staff_role_form.html", {"tab": "roles"})

        Group.objects.get_or_create(name=name)
        messages.success(request, "Роль создана.")
        return redirect("personnel_roles")

    return render(request, "accounts/staff_role_form.html", {"tab": "roles"})


@login_required
def staff_role_edit_view(request, group_id):
    if not can_manage_staff(request.user):
        return _forbidden()

    role = get_object_or_404(Group, id=group_id)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Название роли обязательно.")
            return render(request, "accounts/staff_role_form.html", {"role": role, "tab": "roles"})

        role.name = name
        role.save()
        messages.success(request, "Роль обновлена.")
        return redirect("personnel_roles")

    return render(request, "accounts/staff_role_form.html", {"role": role, "tab": "roles"})


@login_required
def staff_role_delete_view(request, group_id):
    if not can_manage_staff(request.user):
        return _forbidden()

    role = get_object_or_404(Group, id=group_id)

    if request.method == "POST":
        role.delete()
        messages.success(request, "Роль удалена.")
        return redirect("personnel_roles")

    return render(request, "accounts/staff_role_confirm_delete.html", {"role": role, "tab": "roles"})
