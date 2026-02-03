from __future__ import annotations

from django import template

register = template.Library()


@register.filter(name="get_item")
def get_item(mapping, key):
    """Safely get item from a dict-like mapping.

    Usage in templates:
        {{ my_dict|get_item:some_key }}

    Works with int/str keys; returns None if missing.
    """
    if mapping is None:
        return None

    # Try exact key
    try:
        return mapping.get(key)
    except Exception:
        pass

    # Try to normalize between str/int keys
    try:
        if isinstance(key, str) and key.isdigit():
            return mapping.get(int(key))
    except Exception:
        pass

    try:
        return mapping.get(str(key))
    except Exception:
        return None


@register.filter(name="dash_if_empty")
def dash_if_empty(value):
    """Render an em-dash when value is empty.

    Useful for optional fields (comment, phone, etc.) in tables.

    Examples:
        {{ obj.comment|dash_if_empty }}
    """
    if value is None:
        return "—"
    if isinstance(value, str) and value.strip() == "":
        return "—"
    return value
