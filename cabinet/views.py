from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect

from events.models import Event
from .forms import ProfileForm

from accounts.models import Profile


def _get_primary_role(user):
    if getattr(user, "is_superuser", False):
        return ("Суперадмин", "superadmin")

    group_names = list(user.groups.values_list("name", flat=True))
    if group_names:
        return (group_names[0], "custom")

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

    profile, _ = Profile.objects.get_or_create(user=user)

    q = Q(responsible=user)
    if hasattr(Event, "s_engineer"):
        q = q | Q(s_engineer=user)
    if hasattr(Event, "engineers"):
        q = q | Q(engineers=user)

    qs = (
        Event.objects
        .filter(q)
        .distinct()
        .order_by("start_date", "id")
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

    upcoming.sort(key=lambda x: (x["event"].start_date, x["event"].id))
    past.sort(key=lambda x: (x["event"].start_date, x["event"].id), reverse=True)

    stats = {
        "total": len(upcoming) + len(past),
        "upcoming": len(upcoming),
        "past": len(past),
    }

    role_name, role_slug = _get_primary_role(user)

    return render(request, "cabinet/dashboard.html", {
        "role_name": role_name,
        "role_slug": role_slug,
        "stats": stats,
        "upcoming_events": upcoming,
        "past_events": past,
        "profile": profile,
    })


@login_required
def profile_edit(request):
    user = request.user

    if request.method == "POST":
        # ✅ важно: FILES чтобы сохранялись photo/resume
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль обновлён.")
            return redirect("cabinet:dashboard")
        messages.error(request, "Проверьте форму — есть ошибки.")
    else:
        form = ProfileForm(instance=user)

    role_name, role_slug = _get_primary_role(user)

    return render(request, "cabinet/profile_edit.html", {
        "form": form,
        "role_name": role_name,
        "role_slug": role_slug,
    })


@login_required
def password_change(request):
    messages.info(request, "Смена пароля доступна отдельной кнопкой в кабинете.")
    return redirect("cabinet:dashboard")