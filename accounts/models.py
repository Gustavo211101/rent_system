from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Полный доступ'),
        ('viewer', 'Только просмотр'),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='viewer'
    )
