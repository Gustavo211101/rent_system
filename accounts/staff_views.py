from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, Http404
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
    role = (request.GET.get("role") or "").strip()

    # Активные сверху, заблокированные ниже
    users_qs = User.objects.all().order_by("-is_active", "username")
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

        # ✅ много ролей
        role_ids = request.POST.getlist("roles")
        # совместимость: если вдруг где-то осталось старое поле role_id
        role_id_single = (request.POST.get("role_id") or "").strip()

        if not username or not password:
            messages.error(request, "Нужны username и пароль.")
            return render(
                request,
                "accounts/staff_user_form.html",
                {
                    "tab": "users",
                    "roles": roles,
                    "selected_role_ids": role_ids,
                },
            )

        if User.objects.filter(username=username).exists():
            messages.error(request, "Пользователь с таким username уже существует.")
            return render(
                request,
                "accounts/staff_user_form.html",
                {
                    "tab": "users",
                    "roles": roles,
                    "selected_role_ids": role_ids,
                },
            )

        user = User.objects.create_user(username=username, password=password)
        if hasattr(user, "first_name"):
            user.first_name = first_name
        if hasattr(user, "last_name"):
            user.last_name = last_name
        if hasattr(user, "email"):
            user.email = email
        user.save()

        # ✅ сохраняем группы
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
        {
            "tab": "users",
            "roles": roles,
            "selected_role_ids": [],
        },
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

        # ✅ много ролей
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
    """
    ВАЖНО: пользователей НЕ удаляем физически.
    Вместо удаления — блокировка is_active=False (повторно — разблокировка).
    """
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)

    if getattr(user_obj, "is_superuser", False):
        return HttpResponseForbidden("Суперпользователя блокируем только через админку.")

    if user_obj.id == request.user.id:
        return HttpResponseForbidden("Нельзя заблокировать самого себя.")

    is_active = getattr(user_obj, "is_active", True)
    action = "block" if is_active else "unblock"

    if request.method == "POST":
        user_obj.is_active = (action == "unblock")
        user_obj.save(update_fields=["is_active"])

        if action == "block":
            messages.success(request, "Пользователь заблокирован.")
        else:
            messages.success(request, "Пользователь разблокирован.")
        return redirect("staff_users")

    if action == "block":
        title = "Блокировка"
        confirm_text = "Точно заблокировать"
        action_button_text = "Заблокировать"
    else:
        title = "Разблокировка"
        confirm_text = "Точно разблокировать"
        action_button_text = "Разблокировать"

    return render(
        request,
        "accounts/staff_confirm_delete.html",
        {
            "tab": "users",
            "title": title,
            "confirm_text": confirm_text,
            "action_button_text": action_button_text,
            "user_obj": user_obj,
            "cancel_url": "staff_users",
        },
    )


@login_required
def staff_role_add_view(request):
    if not can_manage_staff(request.user):
        return _deny()

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Название роли обязательно.")
            return render(request, "accounts/staff_role_form.html", {"tab": "roles"})

        if Group.objects.filter(name=name).exists():
            messages.error(request, "Такая роль уже существует.")
            return render(request, "accounts/staff_role_form.html", {"tab": "roles"})

        Group.objects.create(name=name)
        messages.success(request, "Роль создана.")
        return redirect("staff_roles")

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
            return render(
                request,
                "accounts/staff_role_form.html",
                {"tab": "roles", "role": role},
            )

        if Group.objects.filter(name=name).exclude(id=role.id).exists():
            messages.error(request, "Такая роль уже существует.")
            return render(
                request,
                "accounts/staff_role_form.html",
                {"tab": "roles", "role": role},
            )

        role.name = name
        role.save()
        messages.success(request, "Роль обновлена.")
        return redirect("staff_roles")

    return render(request, "accounts/staff_role_form.html", {"tab": "roles", "role": role})


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


# ============================================================
# ✅ ДОБАВЛЕНО: просмотр анкеты сотрудника + экспорт анкеты в Excel
# ============================================================

def _get_related_profile_object(user_obj):
    """
    Пытаемся найти связанную "анкету/профиль" пользователя в проекте.
    Ничего не ломаем: если модели нет или связь отсутствует — вернём None.
    """
    candidates = [
        "profile",
        "questionnaire",
        "form",
        "staff_profile",
        "employee_profile",
        "personnel_profile",
        " анкета",  # на случай экзотики
    ]
    for attr in candidates:
        try:
            obj = getattr(user_obj, attr, None)
        except Exception:
            obj = None
        if obj is not None:
            return obj
    return None


def _model_to_pairs(model_obj):
    """
    Любую модель Django превращаем в список (label, value) по ВСЕМ полям.
    FileField/ImageField отдаём как url/path (что есть).
    """
    pairs = []
    if model_obj is None:
        return pairs

    try:
        fields = model_obj._meta.fields
    except Exception:
        return pairs

    for f in fields:
        name = getattr(f, "name", "")
        if not name or name in ("id",):
            continue

        # Обычно FK на user называется user/owner/employee — пропускаем, чтобы не дублировать
        if name in ("user", "owner", "employee", "account"):
            continue

        label = getattr(f, "verbose_name", name)
        try:
            val = getattr(model_obj, name)
        except Exception:
            val = ""

        # FileField/ImageField
        try:
            if hasattr(val, "url"):
                val = val.url
            elif hasattr(val, "path"):
                val = val.path
        except Exception:
            pass

        # Datetime/date formatting
        try:
            if hasattr(val, "strftime"):
                # если это date/datetime
                val = val.strftime("%Y-%m-%d %H:%M") if "time" in str(type(val)).lower() else val.strftime("%Y-%m-%d")
        except Exception:
            pass

        pairs.append((str(label), "" if val is None else str(val)))
    return pairs


@login_required
def staff_user_view(request, user_id: int):
    """
    Просмотр анкеты/профиля сотрудника менеджером.
    Ожидаемый шаблон: accounts/staff_user_view.html
    """
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)

    profile_obj = _get_related_profile_object(user_obj)
    user_pairs = _model_to_pairs(user_obj)
    profile_pairs = _model_to_pairs(profile_obj)

    return render(
        request,
        "accounts/staff_user_view.html",
        {
            "tab": "users",
            "user_obj": user_obj,
            "profile_obj": profile_obj,
            "user_pairs": user_pairs,
            "profile_pairs": profile_pairs,
        },
    )


@login_required
def staff_user_export_xlsx(request, user_id: int):
    """
    Экспорт ВСЕЙ анкеты сотрудника (User + связанная анкета) в Excel.
    """
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)
    profile_obj = _get_related_profile_object(user_obj)

    # Собираем пары
    rows = []
    rows.append(("=== АККАУНТ ===", ""))
    rows.extend(_model_to_pairs(user_obj))

    # группы/роли отдельной строкой
    try:
        roles = ", ".join([g.name for g in user_obj.groups.all().order_by("name")])
        rows.append(("Роли (groups)", roles))
    except Exception:
        pass

    rows.append(("", ""))
    rows.append(("=== АНКЕТА ===", ""))

    if profile_obj is None:
        rows.append(("Анкета", "Не найдена (нет связанной модели профиля/анкеты)"))
    else:
        rows.extend(_model_to_pairs(profile_obj))

    # Генерация Excel
    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
    except Exception as e:
        raise Http404(f"openpyxl не доступен: {e}")

    wb = Workbook()
    ws = wb.active
    ws.title = "Анкета"

    ws.append(["Поле", "Значение"])
    for a, b in rows:
        ws.append([a, b])

    # Автоширина
    for col in range(1, 3):
        max_len = 0
        for cell in ws[get_column_letter(col)]:
            try:
                max_len = max(max_len, len(str(cell.value or "")))
            except Exception:
                pass
        ws.column_dimensions[get_column_letter(col)].width = min(max(12, max_len + 2), 70)

    # отдаём файлом
    filename = f"profile_user_{user_obj.id}.xlsx"
    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp