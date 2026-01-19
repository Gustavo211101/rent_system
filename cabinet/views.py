from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect

from events.models import Event

from .forms import ProfileForm


def _get_user_role_names(user):
    """
    Роли берём напрямую из групп пользователя.
    Суперпользователя показываем отдельно.
    """
    roles = list(user.groups.values_list("name", flat=True))

    if user.is_superuser:
        roles.insert(0, "Суперадмин")

    return roles


@login_required
def dashboard(request):
    user = request.user

    events_qs = (
        Event.objects
        .select_related("responsible", "s_engineer")
        .prefetch_related("engineers")
        .filter(
            Q(responsible=user) |
            Q(s_engineer=user) |
            Q(engineers=user)
        )
        .distinct()
        .order_by("-start_date", "-id")
    )

    context = {
        "events": events_qs,
        "role_names": _get_user_role_names(user),
    }
    return render(request, "cabinet/dashboard.html", context)


@login_required
def profile_edit(request):
    user = request.user

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль обновлён.")
            return redirect("cabinet:dashboard")
        else:
            messages.error(request, "Проверьте форму: есть ошибки.")
    else:
        form = ProfileForm(instance=user)

    context = {
        "form": form,
        "role_names": _get_user_role_names(user),
    }
    return render(request, "cabinet/profile_edit.html", context)