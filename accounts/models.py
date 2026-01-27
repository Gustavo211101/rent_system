from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Кастомный пользователь. Суперпользователя выдаём только через админку.
    """

    class Meta(AbstractUser.Meta):
        permissions = [
            ("manage_staff", "Can manage staff (users/roles)"),
        ]
@property
def display_name(self) -> str:
    """Удобное отображаемое имя: 'Имя Фамилия (username)' или username."""
    full = (self.get_full_name() or "").strip()
    if full:
        return f"{full} ({self.username})"
    return self.username

def __str__(self) -> str:
    return self.display_name
