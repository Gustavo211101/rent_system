# inventory/warehouse_import.py
from __future__ import annotations

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
    s = _s(v)
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _status(v: Any) -> str:
    key = _s(v).lower()
    return STATUS_MAP.get(key, StockEquipmentItem.STATUS_STORAGE)


@dataclass
class ImportResult:
    created_types: int = 0
    updated_types: int = 0
    created_items: int = 0
    updated_items: int = 0
    skipped_rows: int = 0
    errors: list[str] = None

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
    Уникальность в твоём проекте гуляет, поэтому используем максимально безопасный ключ:
    category + subcategory + name
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

    # заполняем поля, если они есть в модели (у тебя там есть и power_w, и power_watt)
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
    Ожидаемые колонки (1..11):
    1 категория
    2 подкатегория
    3 наименование
    4 инвентарный номер
    5 статус ('на мероприятии'/'на складе'/'в ремонте')
    6 комментарий
    7 вес
    8 ширина
    9 высота
    10 глубина
    11 энергопотребление
    """
    result = ImportResult()

    for idx, row in enumerate(rows, start=1):
        # row может быть короче/длиннее — нормализуем до 11
        r = list(row)[:11] + [None] * max(0, 11 - len(row))

        cat = _s(r[0])
        subcat = _s(r[1])
        name = _s(r[2])
        inv = _s(r[3])
        status = _status(r[4])
        comment = _s(r[5])

        weight_kg = _f(r[6])
        width_mm = _i(r[7])
        height_mm = _i(r[8])
        depth_mm = _i(r[9])
        power_watt = _i(r[10])

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
            # подстраховка, если есть updated_at/created_at
            if hasattr(item, "updated_at"):
                item.updated_at = timezone.now()
            item.save()

            if item_created:
                result.created_items += 1
            else:
                result.updated_items += 1

        except Exception as e:
            result.errors.append(f"Строка {idx}: ошибка импорта: {e}")

    return result