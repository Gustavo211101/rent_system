from django.urls import path
from . import views
from . import warehouse_views
from . import warehouse_types_views
from . import warehouse_items_views

urlpatterns = [
    # --- Legacy "equipment" URLs (старый склад). Оставляем как есть для совместимости проекта. ---
    path("equipment/", views.equipment_list_all_view, name="equipment_list_all"),
    path("equipment/categories/", views.equipment_list_categories_view, name="equipment_list_categories"),
    path("equipment/category/<int:category_id>/", views.equipment_category_detail_view, name="equipment_category_detail"),

    # ✅ ремонт (legacy)
    path("equipment/repairs/", views.repair_list_view, name="repair_list"),
    path("equipment/repairs/add/", views.repair_create_view, name="repair_add"),
    path("equipment/repairs/<int:repair_id>/close/", views.repair_close_view, name="repair_close"),
    path("equipment/repairs/<int:repair_id>/delete/", views.repair_delete_view, name="repair_delete"),

    # CRUD оборудования (legacy, только менеджер)
    path("equipment/add/", views.equipment_create_view, name="equipment_add"),
    path("equipment/<int:equipment_id>/edit/", views.equipment_update_view, name="equipment_edit"),
    path("equipment/<int:equipment_id>/delete/", views.equipment_delete_view, name="equipment_delete"),

    # CRUD категорий (legacy, только менеджер)
    path("equipment/categories/add/", views.category_create_view, name="category_add"),
    path("equipment/categories/<int:category_id>/edit/", views.category_update_view, name="category_edit"),
    path("equipment/categories/<int:category_id>/delete/", views.category_delete_view, name="category_delete"),

    # ---------- Склад (warehouse, новая модель) ----------
    path("warehouse/", warehouse_types_views.stock_type_list_view, name="stock_type_list"),
    path("warehouse/repairs/", views.stock_repair_list_view, name="stock_repair_list"),

    # ✅ карточка ремонта (чтобы читать заметки крупнее)
    path("warehouse/repairs/<int:repair_id>/", warehouse_items_views.stock_repair_detail_view, name="stock_repair_detail"),

    # Типы оборудования склада
    path("warehouse/types/add/", warehouse_types_views.stock_type_add_view, name="stock_type_add"),
    path("warehouse/types/<int:type_id>/edit/", warehouse_types_views.stock_type_edit_view, name="stock_type_edit"),
    path("warehouse/types/<int:type_id>/delete/", warehouse_types_views.stock_type_delete_view, name="stock_type_delete"),

    # Категории склада
    path("warehouse/categories/", warehouse_views.stock_category_list_view, name="stock_category_list"),
    path("warehouse/categories/add/", warehouse_views.stock_category_add_view, name="stock_category_add"),
    path("warehouse/categories/<int:category_id>/", warehouse_views.stock_category_detail_view, name="stock_category_detail"),
    path("warehouse/categories/<int:category_id>/edit/", warehouse_views.stock_category_edit_view, name="stock_category_edit"),
    path("warehouse/categories/<int:category_id>/delete/", warehouse_views.stock_category_delete_view, name="stock_category_delete"),

    # Подкатегории внутри категории (список + добавление)
    path("warehouse/categories/<int:category_id>/subcategories/", warehouse_views.stock_subcategory_list_view, name="stock_subcategory_list"),
    path("warehouse/categories/<int:category_id>/subcategories/add/", warehouse_views.stock_subcategory_add_view, name="stock_subcategory_add"),

    # JSON для зависимого выбора подкатегории по выбранной категории
    path(
        "warehouse/subcategories/<int:category_id>/",
        warehouse_types_views.stock_subcategories_by_category_view,
        name="stock_subcategories_by_category",
    ),

    # Подкатегория: редактирование/удаление
    path("warehouse/categories/<int:category_id>/subcategories/<int:subcategory_id>/edit/", warehouse_views.stock_subcategory_edit_view, name="stock_subcategory_edit"),
    path("warehouse/categories/<int:category_id>/subcategories/<int:subcategory_id>/delete/", warehouse_views.stock_subcategory_delete_view, name="stock_subcategory_delete"),

    # Единицы типа
    path("warehouse/types/<int:type_id>/items/", warehouse_items_views.stock_items_list_view, name="stock_items_list"),
    path("warehouse/types/<int:type_id>/items/add/", warehouse_items_views.stock_item_add_view, name="stock_item_add"),
    path("warehouse/types/<int:type_id>/items/<int:item_id>/edit/", warehouse_items_views.stock_item_edit_view, name="stock_item_edit"),
    path("warehouse/types/<int:type_id>/items/<int:item_id>/delete/", warehouse_items_views.stock_item_delete_view, name="stock_item_delete"),
    path("warehouse/types/<int:type_id>/items/<int:item_id>/card/", warehouse_items_views.stock_item_card_view, name="stock_item_card"),

    # Исторически url name "qr", но внутри уже BARCODE
    path("warehouse/types/<int:type_id>/items/<int:item_id>/qr/", warehouse_items_views.stock_item_qr_view, name="stock_item_qr"),
    path("warehouse/types/<int:type_id>/items/<int:item_id>/barcode.svg", warehouse_items_views.stock_item_barcode_svg_view, name="stock_item_barcode_svg"),
    path("warehouse/types/<int:type_id>/items/<int:item_id>/label/print/", warehouse_items_views.stock_item_label_print_view, name="stock_item_label_print"),

    # Ремонт (этап 1)
    path("warehouse/types/<int:type_id>/items/<int:item_id>/repair/open/", warehouse_items_views.stock_item_open_repair_view, name="stock_item_repair_open"),
    path("warehouse/types/<int:type_id>/items/<int:item_id>/repair/close/", warehouse_items_views.stock_item_close_repair_view, name="stock_item_repair_close"),

    path("warehouse/import/", warehouse_views.stock_import_view, name="stock_import"),

    # Сканер (штрихкод): скан -> открыть карточку по инвентарнику
    path("warehouse/scan/", warehouse_views.stock_scan_view, name="stock_scan"),
]