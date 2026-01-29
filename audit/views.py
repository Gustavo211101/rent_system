from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.http import HttpResponseForbidden

from accounts.permissions import can_manage_staff  # менеджер или суперадмин
from .models import AuditLog


@login_required
def audit_list_view(request):
    if not can_manage_staff(request.user):
        return HttpResponseForbidden("Нет доступа")

    qs = AuditLog.objects.select_related("actor").all()

    q = (request.GET.get("q") or "").strip()
    action = (request.GET.get("action") or "").strip()
    etype = (request.GET.get("type") or "").strip()

    if action:
        qs = qs.filter(action=action)

    if etype:
        qs = qs.filter(entity_type=etype)

    if q:
        qs = qs.filter(
            Q(entity_type__icontains=q)
            | Q(entity_id__icontains=q)
            | Q(entity_repr__icontains=q)
            | Q(message__icontains=q)
            | Q(actor__username__icontains=q)
            | Q(actor__first_name__icontains=q)
            | Q(actor__last_name__icontains=q)  
        )

    return render(
        request,
        "audit/audit_list.html",
        {
            "logs": qs[:500],  # чтобы не грузить бесконечно
            "q": q,
            "action": action,
            "type": etype,
        },
    )
