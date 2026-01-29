import secrets

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from .permissions import can_manage_staff
from .models import StaffInvite


@login_required
def staff_invite_link_view(request):
    if not can_manage_staff(request.user):
        return HttpResponseForbidden("Недостаточно прав")

    token = secrets.token_urlsafe(32)
    StaffInvite.objects.create(token=token, created_by=request.user)

    link = request.build_absolute_uri(f"/register/{token}/")
    return render(request, "accounts/staff_invite_link.html", {"invite_link": link})
