from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Безопасное получение значения из dict для шаблонов.
    Всегда возвращает список.
    """
    if not dictionary:
        return []
    return dictionary.get(key, [])