from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(DjangoUserAdmin):
    """
    Роли = Django Groups.
    Показываем группы пользователя в списке как "Роли".
    """

    list_display = (
        'username',
        'email',
        'roles',
        'is_staff',
        'is_active',
        'is_superuser',
    )
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'groups')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    filter_horizontal = ('groups', 'user_permissions')

    def roles(self, obj):
        group_names = list(obj.groups.all().values_list('name', flat=True))
        if not group_names:
            return '—'
        return ', '.join(group_names)

    roles.short_description = 'Роли'
