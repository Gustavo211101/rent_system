from django import template

register = template.Library()


@register.filter
def get_item(d: dict, key):
    """
    Безопасно получить значение из словаря в шаблоне.
    Использование:
        {{ counts_map|get_item:type.id }}
    """
    if not d:
        return None
    return d.get(key)


@register.filter
def default_if_none(value, default=""):
    """
    Если None — вернуть default.
    """
    return default if value is None else value