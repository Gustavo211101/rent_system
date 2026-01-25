from .models import Notification


def notifications_unread_count(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"notifications_unread_count": 0}
    return {
        "notifications_unread_count": Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()
    }
