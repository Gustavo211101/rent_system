from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect
from django.contrib import messages

from events.models import Event
from accounts.roles import ROLE_MANAGER, ROLE_SENIOR_ENGINEER, ROLE_ENGINEER


def _get_primary_role(user):
    if getattr(user, "is_superuser", False):
        return ("Суперадмин", "superadmin")

    groups = set(user.groups.values_list("name", flat=True))

    if ROLE_MANAGER in groups:
        return (ROLE_MANAGER, "manager")
    if ROLE_SENIOR_ENGINEER in groups:
        return (ROLE_SENIOR_ENGINEER, "s_engineer")
    if ROLE_ENGINEER in groups:
        return (ROLE_ENGINEER, "engineer")

    return ("—", "unknown")


def _format_date_range(start, end):
    if not end or end == start:
        return start.strftime("%d.%m.%Y")
    return f"{start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}"


def _event_user_role(event, user):
    roles = []
    slugs = []

    if getattr(event, "responsible_id", None) == user.id:
        roles.append("ответственный")
        slugs.append("manager")

    if hasattr(event, "s_engineer_id") and getattr(event, "s_engineer_id", None) == user.id:
        roles.append("старший инженер")
        slugs.append("s_engineer")

    if hasattr(event, "engineers"):
        try:
            if event.engineers.filter(id=user.id).exists():
                roles.append("инженер")
                slugs.append("engineer")
        except Exception:
            pass

    if not roles:
        return ("участник", "unknown")

    return (", ".join(roles), slugs[0])


@login_required
def dashboard(request):
    user = request.user
    today = date.today()

    q = Q(responsible=user)

    if hasattr(Event, "s_engineer"):
        q = q | Q(s_engineer=user)

    if hasattr(Event, "engineers"):
        q = q | Q(engineers=user)

    qs = (
        Event.objects.filter(q)
        .distinct()
        .order_by("-start_date", "-id")
    )

    if hasattr(Event, "s_engineer"):
        qs = qs.select_related("responsible", "s_engineer")
    else:
        qs = qs.select_related("responsible")

    if hasattr(Event, "engineers"):
        qs = qs.prefetch_related("engineers")

    upcoming = []
    past = []

    for ev in qs:
        end = ev.end_date or ev.start_date
        role_name, role_slug = _event_user_role(ev, user)
        item = {
            "event": ev,
            "date_display": _format_date_range(ev.start_date, ev.end_date),
            "role_name": role_name,
            "role_slug": role_slug,
        }

        if end >= today:
            upcoming.append(item)
        else:
            past.append(item)

    stats = {
        "total": len(upcoming) + len(past),
        "upcoming": len(upcoming),
        "past": len(past),
    }

    role_name, role_slug = _get_primary_role(user)

    context = {
        "role_name": role_name,
        "role_slug": role_slug,
        "stats": stats,
        "upcoming_events": upcoming,
        "past_events": past,
    }
    return render(request, "cabinet/dashboard.html", context)


# =========================
# ВРЕМЕННЫЕ ЗАГЛУШКИ
# =========================

@login_required
def profile_edit(request):
    messages.info(request, "Редактирование профиля будет добавлено позже.")
    return redirect("cabinet:dashboard")


@login_required
def password_change(request):
    messages.info(request, "Смена пароля будет добавлена позже.")
    return redirect("cabinet:dashboard")
