def user_can_edit(user) -> bool:
    """
    Простая политика:
    - superuser всегда может
    - группа "Полный доступ" может
    - остальные: только просмотр
    """
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return user.groups.filter(name='Полный доступ').exists()
