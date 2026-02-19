# inventory/warehouse_import.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import StockCategory, StockSubcategory, StockEquipmentType, StockEquipmentItem


STATUS_MAP = {
    "на складе": StockEquipmentItem.STATUS_STORAGE,
    "склад": StockEquipmentItem.STATUS_STORAGE,
    "storage": StockEquipmentItem.STATUS_STORAGE,

    "на мероприятии": StockEquipmentItem.STATUS_EVENT,
    "мероприятие": StockEquipmentItem.STATUS_EVENT,
    "event": StockEquipmentItem.STATUS_EVENT,

    "в ремонте": StockEquipmentItem.STATUS_REPAIR,
    "ремонт": StockEquipmentItem.STATUS_REPAIR,
    "repair": StockEquipmentItem.STATUS_REPAIR,
}


def _s(v: Any) -> str:
    """Normalize cell to string."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def _f(v: Any) -> float | None:
    s = _s(v).replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _i(v: Any) -> int | None:
    s = _s(v).replace(",", ".")
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _status(v: Any) -> str:
    key = _s(v).lower()
    return STATUS_MAP.get(key, StockEquipmentItem.STATUS_STORAGE)


def _parse_kit(v: Any) -> list[str]:
    """Parse kit inventory numbers from a cell. Supports ',', ';', whitespace and newlines."""
    raw = _s(v)
    if not raw:
        return []
    parts = re.split(r"[;,\s]+", raw)
    out: list[str] = []
    seen = set()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


@dataclass
class ImportResult:
    created_types: int = 0
    updated_types: int = 0
    created_items: int = 0
    updated_items: int = 0
    skipped_rows: int = 0
    errors: list[str] | None = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def _get_or_create_category(name: str) -> StockCategory:
    obj, _ = StockCategory.objects.get_or_create(name=name)
    return obj


def _get_or_create_subcategory(category: StockCategory, name: str) -> StockSubcategory:
    obj, _ = StockSubcategory.objects.get_or_create(category=category, name=name)
    return obj


def _get_or_create_type(
    *,
    category: StockCategory,
    subcategory: StockSubcategory | None,
    name: str,
    weight_kg: float | None,
    width_mm: int | None,
    height_mm: int | None,
    depth_mm: int | None,
    power_watt: int | None,
) -> tuple[StockEquipmentType, bool]:
    """
    Возвращает (type_obj, created_bool).
    Уникальность в проекте может меняться, поэтому используем ключ:
    category + subcategory + name.
    """
    qs = StockEquipmentType.objects.filter(category=category, name=name)
    if subcategory is None:
        qs = qs.filter(subcategory__isnull=True)
    else:
        qs = qs.filter(subcategory=subcategory)

    obj = qs.first()
    created = False

    if obj is None:
        obj = StockEquipmentType(category=category, subcategory=subcategory, name=name)
        created = True

    # ТТХ: на уровне ТИПА (у тебя есть разные поля, заполняем если существуют)
    if hasattr(obj, "weight_kg"):
        obj.weight_kg = weight_kg
    if hasattr(obj, "width_mm"):
        obj.width_mm = width_mm
    if hasattr(obj, "height_mm"):
        obj.height_mm = height_mm
    if hasattr(obj, "depth_mm"):
        obj.depth_mm = depth_mm

    if hasattr(obj, "power_watt"):
        obj.power_watt = power_watt
    if hasattr(obj, "power_w"):
        obj.power_w = power_watt

    if hasattr(obj, "dimensions_mm"):
        if width_mm and height_mm and depth_mm:
            obj.dimensions_mm = f"{width_mm}x{height_mm}x{depth_mm}"
        else:
            obj.dimensions_mm = ""

    obj.save()
    return obj, created


def _get_or_create_item(
    *,
    equipment_type: StockEquipmentType,
    inventory_number: str,
) -> tuple[StockEquipmentItem, bool]:
    obj = StockEquipmentItem.objects.filter(inventory_number=inventory_number).first()
    created = False
    if obj is None:
        obj = StockEquipmentItem(equipment_type=equipment_type, inventory_number=inventory_number)
        created = True
    else:
        # если тип поменялся (например, исправили в экселе) — подтянем
        obj.equipment_type = equipment_type
    return obj, created


@transaction.atomic
def import_stock_from_rows(rows: list[list[Any]]) -> ImportResult:
    """
    Канон колонок (1..12):
    1  категория
    2  подкатегория
    3  наименование
    4  инвентарный номер
    5  статус ('на мероприятии'/'на складе'/'в ремонте')
    6  комплект (необязательно). ПУСТО = ОЧИСТИТЬ комплект.
    7  комментарий
    8  вес
    9  ширина
    10 высота
    11 глубина
    12 энергопотребление
    """
    result = ImportResult()

    # inv -> list kit invs (может быть пустым списком = очистить)
    kit_by_inv: dict[str, list[str]] = {}

    # Pass 1: create/update categories/types/items
    for idx, row in enumerate(rows, start=1):
        r = list(row)[:12] + [None] * max(0, 12 - len(row))

        cat = _s(r[0])
        subcat = _s(r[1])
        name = _s(r[2])
        inv = _s(r[3])
        status = _status(r[4])
        kit_list = _parse_kit(r[5])  # if empty cell => []
        comment = _s(r[6])

        weight_kg = _f(r[7])
        width_mm = _i(r[8])
        height_mm = _i(r[9])
        depth_mm = _i(r[10])
        power_watt = _i(r[11])

        # Пропускаем пустые строки / шапку
        if not any([cat, subcat, name, inv, comment]) and inv == "":
            result.skipped_rows += 1
            continue
        if idx == 1 and cat.lower() in {"категория", "category"}:
            result.skipped_rows += 1
            continue

        # обязательные поля
        if not cat or not name or not inv:
            result.errors.append(f"Строка {idx}: пропущены обязательные поля (категория/наименование/инв.номер)")
            continue

        # Пустая колонка 'комплект' должна очищать комплект
        kit_by_inv[inv] = kit_list  # [] => clear

        try:
            category = _get_or_create_category(cat)
            subcategory_obj = None
            if subcat:
                subcategory_obj = _get_or_create_subcategory(category, subcat)

            eq_type, type_created = _get_or_create_type(
                category=category,
                subcategory=subcategory_obj,
                name=name,
                weight_kg=weight_kg,
                width_mm=width_mm,
                height_mm=height_mm,
                depth_mm=depth_mm,
                power_watt=power_watt,
            )
            if type_created:
                result.created_types += 1
            else:
                result.updated_types += 1

            item, item_created = _get_or_create_item(equipment_type=eq_type, inventory_number=inv)
            item.status = status
            item.comment = comment
            if hasattr(item, "updated_at"):
                item.updated_at = timezone.now()
            item.save()

            if item_created:
                result.created_items += 1
            else:
                result.updated_items += 1

        except Exception as e:
            result.errors.append(f"Строка {idx}: ошибка импорта: {e}")

    # Pass 2: apply kits (after all items exist)
    if not hasattr(StockEquipmentItem, "kit_items"):
        if kit_by_inv:
            result.errors.append("В модели StockEquipmentItem нет поля kit_items: добавь миграцию/поле для комплектов.")
        return result

    for inv, kit_invs in kit_by_inv.items():
        parent = StockEquipmentItem.objects.filter(inventory_number=inv).first()
        if not parent:
            continue

        # очистка/перезапись — всегда
        if not kit_invs:
            parent.kit_items.clear()
            continue

        kit_items: list[StockEquipmentItem] = []
        missing: list[str] = []
        for kinv in kit_invs:
            if kinv == inv:
                continue
            obj = StockEquipmentItem.objects.filter(inventory_number=kinv).first()
            if obj:
                kit_items.append(obj)
            else:
                missing.append(kinv)

        parent.kit_items.set(kit_items)

        if missing:
            result.errors.append(f"Инв. {inv}: элементы комплекта не найдены и пропущены: {', '.join(missing)}")

    return result