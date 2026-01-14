from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .permissions import can_manage_staff

User = get_user_model()


def _deny():
    return HttpResponseForbidden("Недостаточно прав")


@login_required
def staff_users_view(request):
    if not can_manage_staff(request.user):
        return _deny()

    q = (request.GET.get("q") or "").strip()
    role_id = (request.GET.get("role") or "").strip()

    users = User.objects.all().order_by("username")

    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        )

    roles = Group.objects.all().order_by("name")

    if role_id.isdigit():
        users = users.filter(groups__id=int(role_id))

    return render(request, "accounts/staff_users.html", {
        "tab": "users",
        "users": users,
        "roles": roles,
        "q": q,
        "role": role_id,
    })


@login_required
def staff_user_add_view(request):
    if not can_manage_staff(request.user):
        return _deny()

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
            return render(request, "accounts/staff_user_form.html", {
                "tab": "users",
                "roles": roles,
            })

        if User.objects.filter(username=username).exists():
            messages.error(request, "Пользователь с таким username уже существует.")
            return render(request, "accounts/staff_user_form.html", {
                "tab": "users",
                "roles": roles,
            })

        user = User.objects.create_user(username=username, password=password)

        # заполним стандартные поля, если они есть в кастомной модели
        for field, value in (("first_name", first_name), ("last_name", last_name), ("email", email)):
            if hasattr(user, field):
                setattr(user, field, value)
        user.save()

        user.groups.clear()
        if role_id.isdigit():
            grp = Group.objects.filter(id=int(role_id)).first()
            if grp:
                user.groups.add(grp)

        messages.success(request, "Пользователь создан.")
        return redirect("personnel")

    return render(request, "accounts/staff_user_form.html", {
        "tab": "users",
        "roles": roles,
    })


@login_required
def staff_user_edit_view(request, user_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)
    roles = Group.objects.all().order_by("name")

    # суперпользователя — только через админку
    if getattr(user_obj, "is_superuser", False):
        return HttpResponseForbidden("Суперпользователя редактируем только через админку.")

    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        role_id = (request.POST.get("role_id") or "").strip()
        new_password = (request.POST.get("password") or "").strip()

        if hasattr(user_obj, "first_name"):
            user_obj.first_name = first_name
        if hasattr(user_obj, "last_name"):
            user_obj.last_name = last_name
        if hasattr(user_obj, "email"):
            user_obj.email = email

        if new_password:
            user_obj.set_password(new_password)

        user_obj.groups.clear()
        if role_id.isdigit():
            grp = Group.objects.filter(id=int(role_id)).first()
            if grp:
                user_obj.groups.add(grp)

        user_obj.save()
        messages.success(request, "Пользователь обновлён.")
        return redirect("personnel")

    current_role = user_obj.groups.first()

    return render(request, "accounts/staff_user_form.html", {
        "tab": "users",
        "user_obj": user_obj,
        "roles": roles,
        "current_role": current_role,
    })


@login_required
def staff_user_delete_view(request, user_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)

    if getattr(user_obj, "is_superuser", False):
        return HttpResponseForbidden("Суперпользователя удалять нельзя отсюда.")

    if request.method == "POST":
        if user_obj.pk == request.user.pk:
            messages.error(request, "Нельзя удалить самого себя.")
            return redirect("personnel")

        user_obj.delete()
        messages.success(request, "Пользователь удалён.")
        return redirect("personnel")

    return render(request, "accounts/staff_user_confirm_delete.html", {
        "tab": "users",
        "user_obj": user_obj,
    })


@login_required
def staff_roles_view(request):
    if not can_manage_staff(request.user):
        return _deny()

    roles = Group.objects.all().order_by("name")
    return render(request, "accounts/staff_roles.html", {
        "tab": "roles",
        "roles": roles,
    })


@login_required
def staff_role_add_view(request):
    if not can_manage_staff(request.user):
        return _deny()

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
def staff_role_edit_view(request, group_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    role = get_object_or_404(Group, id=group_id)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Название роли обязательно.")
            return render(request, "accounts/staff_role_form.html", {"tab": "roles", "role": role})

        role.name = name
        role.save()
        messages.success(request, "Роль обновлена.")
        return redirect("personnel_roles")

    return render(request, "accounts/staff_role_form.html", {"tab": "roles", "role": role})


@login_required
def staff_role_delete_view(request, group_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    role = get_object_or_404(Group, id=group_id)

    if request.method == "POST":
        role.delete()
        messages.success(request, "Роль удалена.")
        return redirect("personnel_roles")

    return render(request, "accounts/staff_role_confirm_delete.html", {"tab": "roles", "role": role})
