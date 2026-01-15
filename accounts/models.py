from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Кастомный пользователь. Суперпользователя выдаём только через админку.
    """

    class Meta(AbstractUser.Meta):
        permissions = [
            ("manage_staff", "Can manage staff (users/roles)"),
        ]
