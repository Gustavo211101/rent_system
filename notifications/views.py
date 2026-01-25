from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_GET, require_POST

from .models import Notification


def _serialize(n: Notification):
    return {
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "url": n.url,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat(),
    }


@require_GET
@login_required
def api_list(request):
    qs = Notification.objects.filter(recipient=request.user).order_by("-created_at", "-id")[:30]
    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({"ok": True, "unread_count": unread, "items": [_serialize(n) for n in qs]})


@require_POST
@login_required
def api_mark_read(request, notification_id: int):
    Notification.objects.filter(recipient=request.user, id=notification_id).update(is_read=True)
    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({"ok": True, "unread_count": unread})


@require_POST
@login_required
def api_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True, "unread_count": 0})


@require_POST
@login_required
def api_delete(request, notification_id: int):
    Notification.objects.filter(recipient=request.user, id=notification_id).delete()
    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({"ok": True, "unread_count": unread})
