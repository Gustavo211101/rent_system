from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .permissions import can_manage_staff

User = get_user_model()


def _deny():
    return HttpResponseForbidden("Недостаточно прав")


def _permission_choices():
    """
    Возвращает список для чекбоксов прав:
    (perm_id, "app_label: Permission name")
    """
    perms_qs = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label", "codename"
    )
    out = []
    for p in perms_qs:
        label = f"{p.content_type.app_label}: {p.name}"
        out.append((str(p.id), label))
    return out


@login_required
def staff_users_view(request):
    if not can_manage_staff(request.user):
        return _deny()

    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()

    users_qs = User.objects.all().order_by("username")
    roles = Group.objects.all().order_by("name")

    if q:
        users_qs = users_qs.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
        )

    if role.isdigit():
        users_qs = users_qs.filter(groups__id=int(role)).distinct()

    return render(
        request,
        "accounts/staff_users.html",
        {"tab": "users", "users": users_qs, "q": q, "roles": roles, "role": role},
    )


@login_required
def staff_roles_view(request):
    if not can_manage_staff(request.user):
        return _deny()

    roles = Group.objects.all().order_by("name")
    return render(request, "accounts/staff_roles.html", {"tab": "roles", "roles": roles})


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

        role_ids = request.POST.getlist("roles")
        role_id_single = (request.POST.get("role_id") or "").strip()

        if not username or not password:
            messages.error(request, "Нужны username и пароль.")
            return render(
                request,
                "accounts/staff_user_form.html",
                {"tab": "users", "roles": roles, "selected_role_ids": role_ids},
            )

        if User.objects.filter(username=username).exists():
            messages.error(request, "Пользователь с таким username уже существует.")
            return render(
                request,
                "accounts/staff_user_form.html",
                {"tab": "users", "roles": roles, "selected_role_ids": role_ids},
            )

        user = User.objects.create_user(username=username, password=password)
        if hasattr(user, "first_name"):
            user.first_name = first_name
        if hasattr(user, "last_name"):
            user.last_name = last_name
        if hasattr(user, "email"):
            user.email = email
        user.save()

        user.groups.clear()

        chosen = []
        for rid in role_ids:
            if str(rid).isdigit():
                chosen.append(int(rid))
        if not chosen and role_id_single.isdigit():
            chosen = [int(role_id_single)]

        if chosen:
            user.groups.add(*Group.objects.filter(id__in=chosen))

        messages.success(request, "Пользователь создан.")
        return redirect("staff_users")

    return render(
        request,
        "accounts/staff_user_form.html",
        {"tab": "users", "roles": roles, "selected_role_ids": []},
    )


@login_required
def staff_user_edit_view(request, user_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)
    roles = Group.objects.all().order_by("name")

    if getattr(user_obj, "is_superuser", False):
        return HttpResponseForbidden("Суперпользователя редактируем только через админку.")

    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()

        role_ids = request.POST.getlist("roles")
        role_id_single = (request.POST.get("role_id") or "").strip()

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

        chosen = []
        for rid in role_ids:
            if str(rid).isdigit():
                chosen.append(int(rid))
        if not chosen and role_id_single.isdigit():
            chosen = [int(role_id_single)]

        if chosen:
            user_obj.groups.add(*Group.objects.filter(id__in=chosen))

        user_obj.save()
        messages.success(request, "Пользователь обновлён.")
        return redirect("staff_users")

    selected_role_ids = [str(g.id) for g in user_obj.groups.all()]

    return render(
        request,
        "accounts/staff_user_form.html",
        {
            "tab": "users",
            "user_obj": user_obj,
            "roles": roles,
            "selected_role_ids": selected_role_ids,
        },
    )


@login_required
def staff_user_delete_view(request, user_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)

    if getattr(user_obj, "is_superuser", False):
        return HttpResponseForbidden("Суперпользователя удаляем только через админку.")

    if request.method == "POST":
        user_obj.delete()
        messages.success(request, "Пользователь удалён.")
        return redirect("staff_users")

    # ✅ даём шаблону все нужные переменные
    return render(
        request,
        "accounts/staff_confirm_delete.html",
        {
            "tab": "users",
            "title": "Удалить пользователя",
            "object_name": user_obj.username,
            "cancel_url": "staff_users",
        },
    )


@login_required
def staff_role_add_view(request):
    if not can_manage_staff(request.user):
        return _deny()

    perm_choices = _permission_choices()

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        selected_perm_ids = request.POST.getlist("perm_ids")

        if not name:
            messages.error(request, "Название роли обязательно.")
            return render(
                request,
                "accounts/staff_role_form.html",
                {"tab": "roles", "perm_choices": perm_choices, "current_perm_ids": selected_perm_ids},
            )

        if Group.objects.filter(name=name).exists():
            messages.error(request, "Такая роль уже существует.")
            return render(
                request,
                "accounts/staff_role_form.html",
                {"tab": "roles", "perm_choices": perm_choices, "current_perm_ids": selected_perm_ids},
            )

        role = Group.objects.create(name=name)

        # ✅ сохраняем права
        perms = Permission.objects.filter(id__in=[int(x) for x in selected_perm_ids if str(x).isdigit()])
        role.permissions.set(perms)

        messages.success(request, "Роль создана.")
        return redirect("staff_roles")

    return render(
        request,
        "accounts/staff_role_form.html",
        {"tab": "roles", "perm_choices": perm_choices, "current_perm_ids": []},
    )


@login_required
def staff_role_edit_view(request, group_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    role = get_object_or_404(Group, id=group_id)
    perm_choices = _permission_choices()
    current_perm_ids = [str(pid) for pid in role.permissions.values_list("id", flat=True)]

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        selected_perm_ids = request.POST.getlist("perm_ids")

        if not name:
            messages.error(request, "Название роли обязательно.")
            return render(
                request,
                "accounts/staff_role_form.html",
                {"tab": "roles", "role": role, "perm_choices": perm_choices, "current_perm_ids": selected_perm_ids},
            )

        if Group.objects.filter(name=name).exclude(id=role.id).exists():
            messages.error(request, "Такая роль уже существует.")
            return render(
                request,
                "accounts/staff_role_form.html",
                {"tab": "roles", "role": role, "perm_choices": perm_choices, "current_perm_ids": selected_perm_ids},
            )

        role.name = name
        role.save()

        perms = Permission.objects.filter(id__in=[int(x) for x in selected_perm_ids if str(x).isdigit()])
        role.permissions.set(perms)

        messages.success(request, "Роль обновлена.")
        return redirect("staff_roles")

    return render(
        request,
        "accounts/staff_role_form.html",
        {"tab": "roles", "role": role, "perm_choices": perm_choices, "current_perm_ids": current_perm_ids},
    )


@login_required
def staff_role_delete_view(request, group_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    role = get_object_or_404(Group, id=group_id)

    if User.objects.filter(groups=role).exists():
        if request.method == "POST":
            messages.error(request, "Нельзя удалить роль: она назначена пользователям.")
            return redirect("staff_roles")
        return render(
            request,
            "accounts/staff_role_confirm_delete.html",
            {"tab": "roles", "role": role, "has_users": True},
        )

    if request.method == "POST":
        role.delete()
        messages.success(request, "Роль удалена.")
        return redirect("staff_roles")

    return render(
        request,
        "accounts/staff_role_confirm_delete.html",
        {"tab": "roles", "role": role, "has_users": False},
    )