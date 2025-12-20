from django.utils import timezone
from .models import Event


def auto_close_past_events():
    now = timezone.now()
    Event.objects.filter(
        status__in=['draft', 'confirmed', 'in_rent'],
        date_end__lt=now
    ).update(status=Event.STATUS_CLOSED)
