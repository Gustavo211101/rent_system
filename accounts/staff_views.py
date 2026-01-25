from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .permissions import can_manage_staff

User = get_user_model()

PERM_CODES = [
    ("accounts.manage_staff", "Управление персоналом и ролями"),
    ("inventory.manage_inventory", "Оборудование (CRUD)"),
    ("events.edit_event_card", "Мероприятия: карточка/статус/даты"),
    ("events.edit_event_equipment", "Мероприятия: оборудование/аренда"),
]


def _deny():
    return HttpResponseForbidden("Недостаточно прав")


def _perm_objects():
    result = []
    for code, label in PERM_CODES:
        app_label, codename = code.split(".", 1)
        p = Permission.objects.filter(content_type__app_label=app_label, codename=codename).first()
        result.append((code, label, p))
    return result


@login_required
def staff_users_view(request):
    if not can_manage_staff(request.user):
        return _deny()

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

    roles = Group.objects.all().order_by("name")
    if role_id.isdigit():
        users = users.filter(groups__id=int(role_id))

    return render(
        request,
        "accounts/staff_users.html",
        {
            "tab": "users",
            "users": users,
            "roles": roles,
            "q": q,
            "role": role_id,
        },
    )


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
            return render(request, "accounts/staff_user_form.html", {"tab": "users", "roles": roles})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Пользователь с таким username уже существует.")
            return render(request, "accounts/staff_user_form.html", {"tab": "users", "roles": roles})

        user = User.objects.create_user(username=username, password=password)
        if hasattr(user, "first_name"):
            user.first_name = first_name
        if hasattr(user, "last_name"):
            user.last_name = last_name
        if hasattr(user, "email"):
            user.email = email
        user.save()

        # 1 роль = 1 группа
        user.groups.clear()
        if role_id.isdigit():
            grp = Group.objects.filter(id=int(role_id)).first()
            if grp:
                user.groups.add(grp)

        messages.success(request, "Пользователь создан.")
        return redirect("staff_users")

    return render(
        request,
        "accounts/staff_user_form.html",
        {
            "tab": "users",
            "roles": roles,
            "user_obj": None,
            "current_role": None,
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
        return redirect("staff_users")

    current_role = user_obj.groups.first()

    return render(
        request,
        "accounts/staff_user_form.html",
        {
            "tab": "users",
            "roles": roles,
            "user_obj": user_obj,
            "current_role": current_role,
        },
    )


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
            return redirect("staff_users")

        user_obj.delete()
        messages.success(request, "Пользователь удалён.")
        return redirect("staff_users")

    return render(
        request,
        "accounts/staff_user_confirm_delete.html",
        {
            "tab": "users",
            "user_obj": user_obj,
        },
    )


@login_required
def staff_roles_view(request):
    if not can_manage_staff(request.user):
        return _deny()

    roles = Group.objects.all().order_by("name")
    return render(request, "accounts/staff_roles.html", {"tab": "roles", "roles": roles})


@login_required
def staff_role_add_view(request):
    if not can_manage_staff(request.user):
        return _deny()

    perms = _perm_objects()

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        selected = set(request.POST.getlist("perms"))

        if not name:
            messages.error(request, "Название роли обязательно.")
            return render(request, "accounts/staff_role_form.html", {"tab": "roles", "perms": perms})

        role, _ = Group.objects.get_or_create(name=name)
        role.permissions.clear()

        for code, label, p in perms:
            if code in selected and p:
                role.permissions.add(p)

        messages.success(request, "Роль создана.")
        return redirect("staff_roles")

    return render(
        request,
        "accounts/staff_role_form.html",
        {"tab": "roles", "perms": perms, "role": None, "current_codes": set()},
    )


@login_required
def staff_role_edit_view(request, group_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    role = get_object_or_404(Group, id=group_id)
    perms = _perm_objects()

    current_codes = set()
    for code, label, p in perms:
        if p and role.permissions.filter(id=p.id).exists():
            current_codes.add(code)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        selected = set(request.POST.getlist("perms"))

        if not name:
            messages.error(request, "Название роли обязательно.")
            return render(
                request,
                "accounts/staff_role_form.html",
                {"tab": "roles", "role": role, "perms": perms, "current_codes": current_codes},
            )

        role.name = name
        role.save()

        role.permissions.clear()
        for code, label, p in perms:
            if code in selected and p:
                role.permissions.add(p)

        messages.success(request, "Роль обновлена.")
        return redirect("staff_roles")

    return render(
        request,
        "accounts/staff_role_form.html",
        {"tab": "roles", "role": role, "perms": perms, "current_codes": current_codes},
    )


@login_required
def staff_role_delete_view(request, group_id: int):
    if not can_manage_staff(request.user):
        return _deny()

    role = get_object_or_404(Group, id=group_id)

    # ✅ Защита: если роль назначена пользователям — не даём удалить
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


# =========================
# Календарь занятости (персонал)
# =========================
import calendar as _pycalendar
from datetime import date as _date
from collections import defaultdict as _defaultdict

from events.models import Event as _Event


def _parse_year_month_staff(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
    except Exception:
        year = today.year
    try:
        month = int(request.GET.get("month", today.month))
    except Exception:
        month = today.month
    if month < 1:
        month = 1
    if month > 12:
        month = 12
    return year, month


def _pack_lanes_staff(segments):
    lanes = []  # list[list[(start,end)]]
    for seg in sorted(segments, key=lambda s: (s["start_col"], s["end_col"], s["event"].id)):
        placed = False
        for lane_idx, used in enumerate(lanes):
            conflict = False
            for a, b in used:
                if not (seg["end_col"] < a or seg["start_col"] > b):
                    conflict = True
                    break
            if not conflict:
                seg["lane"] = lane_idx
                used.append((seg["start_col"], seg["end_col"]))
                placed = True
                break
        if not placed:
            seg["lane"] = len(lanes)
            lanes.append([(seg["start_col"], seg["end_col"])])
    return segments


@login_required
def staff_availability_calendar_view(request):
    if not can_manage_staff(request.user):
        return _deny()

    # выбранный пользователь
    selected_user_id = request.GET.get("user_id") or ""
    selected_user = None
    if selected_user_id:
        try:
            selected_user = User.objects.filter(id=int(selected_user_id)).first()
        except Exception:
            selected_user = None

    # для выпадашки — все пользователи
    users_qs = User.objects.all().order_by("username")

    year, month = _parse_year_month_staff(request)

    month_days = list(_pycalendar.Calendar(firstweekday=0).monthdatescalendar(year, month))
    grid_start = month_days[0][0]
    grid_end = month_days[-1][-1]

    week_segments = {}

    if selected_user:
        q = Q(responsible=selected_user)

        if hasattr(_Event, "s_engineer"):
            q = q | Q(s_engineer=selected_user)

        if hasattr(_Event, "engineers"):
            q = q | Q(engineers=selected_user)

        ev_qs = (
            _Event.objects
            .filter(q)
            .distinct()
            .filter(start_date__lte=grid_end, end_date__gte=grid_start)
            .order_by("start_date", "id")
        )

        # исключаем soft-deleted если поле есть
        if hasattr(_Event, "is_deleted"):
            ev_qs = ev_qs.filter(is_deleted=False)

        for week in month_days:
            week_start = week[0]
            week_end = week[-1]

            segs = []
            for e in ev_qs:
                seg_start = max(e.start_date, week_start, grid_start)
                seg_end = min(e.end_date, week_end, grid_end)
                if seg_end < seg_start:
                    continue

                start_col = week.index(seg_start)
                end_col = week.index(seg_end)

                segs.append({
                    "event": e,
                    "start_col": start_col,
                    "end_col": end_col,
                    "span": (end_col - start_col + 1),
                    "cont_left": e.start_date < week_start,
                    "cont_right": e.end_date > week_end,
                    "data_start": e.start_date.strftime("%Y-%m-%d"),
                    "data_end": e.end_date.strftime("%Y-%m-%d"),
                })

            segs = _pack_lanes_staff(segs)
            week_segments[week_start] = segs

    context = {
        "tab": "availability",
        "users": users_qs,
        "selected_user": selected_user,
        "selected_user_id": str(selected_user.id) if selected_user else "",
        "year": year,
        "month": month,
        "month_name": _pycalendar.month_name[month],
        "month_days": month_days,
        "week_segments": week_segments,
    }
    return render(request, "accounts/personnel_availability_calendar.html", context)
