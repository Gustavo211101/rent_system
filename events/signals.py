from django.db.models.signals import m2m_changed, pre_save, post_save
from django.dispatch import receiver
from django.urls import reverse

from django.contrib.auth import get_user_model

from .models import Event
from notifications.models import Notification

User = get_user_model()


def _notify(user_id: int, event: Event, title: str, message: str):
    if not user_id:
        return
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    url = ""
    try:
        url = reverse("event_detail", kwargs={"event_id": event.id})
    except Exception:
        # fallback if name differs
        try:
            url = reverse("event_detail", args=[event.id])
        except Exception:
            url = ""

    Notification.objects.create(
        recipient=user,
        event=event,
        title=title,
        message=message,
        url=url,
    )


@receiver(pre_save, sender=Event)
def _event_track_old(sender, instance: Event, **kwargs):
    if not instance.pk:
        instance._old_responsible_id = None
        instance._old_s_engineer_id = None
        return
    try:
        old = Event.objects.get(pk=instance.pk)
        instance._old_responsible_id = old.responsible_id
        instance._old_s_engineer_id = getattr(old, "s_engineer_id", None)
    except Event.DoesNotExist:
        instance._old_responsible_id = None
        instance._old_s_engineer_id = None


@receiver(post_save, sender=Event)
def _event_notify_role_changes(sender, instance: Event, created: bool, **kwargs):
    # On create: notify assigned users
    if created:
        if instance.responsible_id:
            _notify(instance.responsible_id, instance, "Назначение на мероприятие", f"Вы назначены ответственным на «{instance.name}».")
        if getattr(instance, "s_engineer_id", None):
            _notify(instance.s_engineer_id, instance, "Назначение на мероприятие", f"Вы назначены старшим инженером на «{instance.name}».")
        return

    old_res = getattr(instance, "_old_responsible_id", None)
    new_res = instance.responsible_id
    if old_res != new_res:
        if old_res:
            _notify(old_res, instance, "Изменение участия", f"Вы сняты с роли ответственного в «{instance.name}».")
        if new_res:
            _notify(new_res, instance, "Назначение на мероприятие", f"Вы назначены ответственным на «{instance.name}».")

    old_se = getattr(instance, "_old_s_engineer_id", None)
    new_se = getattr(instance, "s_engineer_id", None)
    if old_se != new_se:
        if old_se:
            _notify(old_se, instance, "Изменение участия", f"Вы сняты с роли старшего инженера в «{instance.name}».")
        if new_se:
            _notify(new_se, instance, "Назначение на мероприятие", f"Вы назначены старшим инженером на «{instance.name}».")


@receiver(m2m_changed, sender=Event.engineers.through)
def _event_engineers_changed(sender, instance: Event, action: str, pk_set, **kwargs):
    if action == "post_add":
        for uid in pk_set:
            _notify(uid, instance, "Добавлены в мероприятие", f"Вы добавлены инженером в «{instance.name}».")
    elif action == "post_remove":
        for uid in pk_set:
            _notify(uid, instance, "Удалены из мероприятия", f"Вы удалены из инженеров в «{instance.name}».")
