from __future__ import annotations

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile_exists(sender, instance, created, **kwargs):
    """Гарантируем, что у каждого пользователя есть Profile."""
    if created:
        Profile.objects.create(user=instance)
        return

    # На случай старых пользователей (до ввода профилей)
    try:
        instance.profile
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)