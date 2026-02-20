from django.contrib import admin

# В проекте было много итераций, поэтому делаем импорт максимально устойчивым:
# регистрируем в админке только те модели, которые реально существуют.
try:
    from . import models as m
except Exception:
    m = None


def _has(name: str) -> bool:
    return bool(m) and hasattr(m, name)


# ---------- БАЗОВЫЕ (legacy) модели (если вдруг нужны) ----------
if _has("EquipmentCategory"):
    @admin.register(m.EquipmentCategory)
    class EquipmentCategoryAdmin(admin.ModelAdmin):
        search_fields = ("name",)
        list_display = ("id", "name")
        ordering = ("name", "id")


if _has("Equipment"):
    @admin.register(m.Equipment)
    class EquipmentAdmin(admin.ModelAdmin):
        search_fields = ("name", "serial_number")
        list_filter = ("status", "category")
        list_display = ("id", "name", "category", "status", "quantity_total")
        ordering = ("name", "id")


if _has("EquipmentRepair"):
    @admin.register(m.EquipmentRepair)
    class EquipmentRepairAdmin(admin.ModelAdmin):
        list_filter = ("status", "start_date", "end_date")
        search_fields = ("equipment__name", "note")
        list_display = ("id", "equipment", "quantity", "status", "start_date", "end_date")
        ordering = ("-created_at", "-id")


# ---------- НОВЫЙ СКЛАД (warehouse) ----------
# Категория склада
if _has("StockCategory"):
    @admin.register(m.StockCategory)
    class StockCategoryAdmin(admin.ModelAdmin):
        search_fields = ("name",)
        list_display = ("id", "name")
        ordering = ("name", "id")


# Подкатегория склада
if _has("StockSubcategory"):
    @admin.register(m.StockSubcategory)
    class StockSubcategoryAdmin(admin.ModelAdmin):
        search_fields = ("name", "category__name")
        list_filter = ("category",)
        list_display = ("id", "category", "name")
        ordering = ("category__name", "name", "id")


# Inline для единиц внутри типа
class _StockEquipmentItemInline(admin.TabularInline):
    extra = 0
    show_change_link = True

    def get_model(self):
        return getattr(m, "StockEquipmentItem", None)

    @property
    def model(self):
        return self.get_model()

    # Django требует атрибут model, но мы делаем безопасно:
    # если модели нет, инлайн не подключаем.
    can_delete = True


# Тип оборудования склада
if _has("StockEquipmentType"):
    class StockEquipmentTypeAdmin(admin.ModelAdmin):
        search_fields = ("name", "category__name", "subcategory__name")
        list_filter = ("category", "subcategory", "is_active") if hasattr(m.StockEquipmentType, "is_active") else ("category", "subcategory")
        list_display = ("id", "name", "category", "subcategory", "created_at") if hasattr(m.StockEquipmentType, "created_at") else ("id", "name", "category", "subcategory")
        ordering = ("category__name", "subcategory__name", "name", "id")

        def get_inlines(self, request, obj):
            # Подключаем inline только если модель StockEquipmentItem существует
            if _has("StockEquipmentItem"):
                return [_StockEquipmentItemInline]
            return []

    admin.site.register(m.StockEquipmentType, StockEquipmentTypeAdmin)


# Единицы (инвентарники)
if _has("StockEquipmentItem"):
    @admin.register(m.StockEquipmentItem)
    class StockEquipmentItemAdmin(admin.ModelAdmin):
        search_fields = ("inventory_number", "equipment_type__name", "equipment_type__category__name", "equipment_type__subcategory__name")
        list_filter = ("status", "equipment_type__category") if hasattr(m.StockEquipmentItem, "status") else ("equipment_type__category",)
        list_select_related = ("equipment_type", "equipment_type__category", "equipment_type__subcategory")
        list_display = (
            "id",
            "inventory_number",
            "equipment_type",
            "status",
            "comment",
            "created_at",
        ) if hasattr(m.StockEquipmentItem, "created_at") else (
            "id",
            "inventory_number",
            "equipment_type",
            "status",
            "comment",
        )
        ordering = ("inventory_number", "id")

        # Если у тебя есть ManyToMany kit_items — удобно редактировать прямо в админке
        filter_horizontal = ("kit_items",) if hasattr(m.StockEquipmentItem, "kit_items") else ()

        def get_queryset(self, request):
            qs = super().get_queryset(request)
            # чтобы не было N+1 запросов
            try:
                return qs.select_related("equipment_type", "equipment_type__category", "equipment_type__subcategory")
            except Exception:
                return qs


# Ремонты склада
if _has("StockRepair"):
    @admin.register(m.StockRepair)
    class StockRepairAdmin(admin.ModelAdmin):
        # названия полей в проекте менялись — покажем максимум, что есть
        list_display = ["id"]
        list_filter = []
        search_fields = []
        ordering = ["-id"]

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # собираем динамически по доступным полям
            fields = {f.name for f in self.model._meta.fields}

            if "equipment_item" in fields:
                self.list_display += ["equipment_item"]
                self.search_fields += ["equipment_item__inventory_number", "equipment_item__equipment_type__name"]
                self.list_filter += ["equipment_item__status"] if _has("StockEquipmentItem") and hasattr(m.StockEquipmentItem, "status") else []
            elif "item" in fields:
                self.list_display += ["item"]
                self.search_fields += ["item__inventory_number", "item__equipment_type__name"]

            for f in ["opened_at", "closed_at", "created_at"]:
                if f in fields:
                    self.list_display += [f]
                    self.list_filter += [f]
                    break

            for f in ["reason", "note"]:
                if f in fields:
                    self.list_display += [f]
                    self.search_fields += [f]
                    break

            for f in ["close_note", "is_closed", "status"]:
                if f in fields:
                    self.list_display += [f]
                    self.list_filter += [f]
                    break

            if "opened_by" in fields:
                self.list_display += ["opened_by"]
            if "closed_by" in fields:
                self.list_display += ["closed_by"]

        def get_queryset(self, request):
            qs = super().get_queryset(request)
            # если есть select_related поля — подтянем
            try:
                if hasattr(self.model, "equipment_item"):
                    return qs.select_related("equipment_item", "equipment_item__equipment_type")
                if hasattr(self.model, "item"):
                    return qs.select_related("item", "item__equipment_type")
            except Exception:
                return qs
            return qs