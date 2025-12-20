from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Роли и права управляются через Django Groups/Permissions.
    """
    pass
