from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # Создадим базовые группы, если их нет (без миграций)
        try:
            from django.contrib.auth.models import Group
            from .roles import ALL_ROLES

            for role in ALL_ROLES:
                Group.objects.get_or_create(name=role)
        except Exception:
            # При миграциях/первом старте база может быть не готова — это нормально
            pass

        # ✅ Профили сотрудников (post_save)
        try:
            from . import profile_signals  # noqa: F401
        except Exception:
            # при миграциях база/модели могут быть в промежуточном состоянии
            pass