from __future__ import annotations

import io
import os
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from .permissions import can_manage_staff
from .models import Profile

User = get_user_model()


def _deny():
    return HttpResponseForbidden("Недостаточно прав")


def _full_name(u: User) -> str:
    parts = []
    for attr in ("last_name", "first_name", "patronymic"):
        v = getattr(u, attr, "") or ""
        v = v.strip()
        if v:
            parts.append(v)
    return " ".join(parts) if parts else (u.username or "—")


def _auto_width(ws, max_cols=2):
    for col in range(1, max_cols + 1):
        max_len = 0
        for row in range(1, ws.max_row + 1):
            val = ws.cell(row=row, column=col).value
            if val is None:
                continue
            max_len = max(max_len, len(str(val)))
        ws.column_dimensions[get_column_letter(col)].width = min(max(14, max_len + 2), 80)


def _model_field_label(model, field_name: str) -> str:
    try:
        f = model._meta.get_field(field_name)
        return str(getattr(f, "verbose_name", field_name))
    except Exception:
        return field_name


def _value_to_cell_str(instance, field_name: str):
    """
    Возвращает "человекочитаемое" значение:
    - choices -> display
    - FileField/ImageField -> имя файла (+ url если можно)
    - остальное -> str(value)
    """
    # choices display
    getter = getattr(instance, f"get_{field_name}_display", None)
    if callable(getter):
        try:
            disp = getter()
            if disp:
                return disp
        except Exception:
            pass

    val = getattr(instance, field_name, "")
    if val is None:
        return ""

    # FileField / ImageField
    # У Django у них есть .name и часто .url
    if hasattr(val, "name") and hasattr(val, "file"):
        name = getattr(val, "name", "") or ""
        url = ""
        try:
            url = val.url  # может упасть если storage без url
        except Exception:
            url = ""
        if name and url:
            return f"{name} | {url}"
        return name or ""

    return str(val)


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
def staff_user_view(request, user_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)
    profile, _ = Profile.objects.get_or_create(user=user_obj)

    return render(
        request,
        "accounts/staff_user_detail.html",
        {"tab": "users", "user_obj": user_obj, "profile": profile, "full_name": _full_name(user_obj)},
    )


@login_required
def staff_user_export_xlsx(request, user_id: int):
    """
    ✅ Экспортирует:
    - лист "Аккаунт" — основные поля User + роли
    - лист "Анкета" — ВСЕ поля модели Profile (автоматически)
    """
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)
    profile, _ = Profile.objects.get_or_create(user=user_obj)

    wb = Workbook()

    # --- Аккаунт ---
    ws1 = wb.active
    ws1.title = "Аккаунт"

    # Важно: не вытаскиваем password / last_login как “таблицу полей”, а даём полезный минимум.
    account_rows = [
        ("ID", user_obj.id),
        ("Username", user_obj.username or ""),
        ("Email", getattr(user_obj, "email", "") or ""),
        ("Фамилия", getattr(user_obj, "last_name", "") or ""),
        ("Имя", getattr(user_obj, "first_name", "") or ""),
        ("Отчество", getattr(user_obj, "patronymic", "") or ""),
        ("Телефон", getattr(user_obj, "phone", "") or ""),
        ("Активен", "Да" if getattr(user_obj, "is_active", False) else "Нет"),
        ("Суперпользователь", "Да" if getattr(user_obj, "is_superuser", False) else "Нет"),
        ("Роли", ", ".join(list(user_obj.groups.values_list("name", flat=True))) or "—"),
        ("Создан", str(getattr(user_obj, "date_joined", "") or "")),
    ]

    for r, (k, v) in enumerate(account_rows, start=1):
        ws1.cell(row=r, column=1, value=k)
        ws1.cell(row=r, column=2, value=v)

    _auto_width(ws1, max_cols=2)

    # --- Анкета: ВСЕ поля Profile ---
    ws2 = wb.create_sheet("Анкета")

    # Берём все concrete поля кроме pk и user (user покажем отдельно)
    profile_fields = []
    for f in Profile._meta.get_fields():
        # пропускаем связи/реверс-отношения и m2m
        if not getattr(f, "concrete", False):
            continue
        if getattr(f, "many_to_many", False):
            continue
        if f.name in ("id", "user"):
            continue
        profile_fields.append(f.name)

    # Чтобы “user” тоже был в анкете как ссылочный текст
    ws2.cell(row=1, column=1, value="Пользователь")
    ws2.cell(row=1, column=2, value=_full_name(user_obj) + f" (@{user_obj.username})")
    row = 2

    for field_name in profile_fields:
        label = _model_field_label(Profile, field_name)
        value = _value_to_cell_str(profile, field_name)
        ws2.cell(row=row, column=1, value=label)
        ws2.cell(row=row, column=2, value=value)
        row += 1

    _auto_width(ws2, max_cols=2)

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)

    filename = f"анкета_{user_obj.username}.xlsx"
    resp = HttpResponse(
        out.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@login_required
def staff_user_resume_download(request, user_id: int):
    """Скачивание резюме как оригинальный файл (не Excel)."""
    if not can_manage_staff(request.user):
        return _deny()

    user_obj = get_object_or_404(User, id=user_id)
    profile, _ = Profile.objects.get_or_create(user=user_obj)

    if not profile.resume:
        raise Http404("Резюме не загружено")

    try:
        f = profile.resume.open("rb")
    except Exception:
        raise Http404("Не удалось открыть файл резюме")

    base = os.path.basename(profile.resume.name)
    resp = FileResponse(f, as_attachment=True, filename=base)
    return resp


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
        {"tab": "users", "user_obj": user_obj, "roles": roles, "selected_role_ids": selected_role_ids},
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

    return render(request, "accounts/staff_confirm_delete.html", {"tab": "users", "user_obj": user_obj})


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
            return render(request, "accounts/staff_role_form.html", {"tab": "roles", "role": role})

        if Group.objects.filter(name=name).exclude(id=role.id).exists():
            messages.error(request, "Такая роль уже существует.")
            return render(request, "accounts/staff_role_form.html", {"tab": "roles", "role": role})

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