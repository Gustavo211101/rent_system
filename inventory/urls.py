from django.urls import path
from . import views
from . import warehouse_views

urlpatterns = [
    # существующие страницы просмотра
    path("equipment/", views.equipment_list_all_view, name="equipment_list_all"),
    path("equipment/categories/", views.equipment_list_categories_view, name="equipment_list_categories"),
    path("equipment/category/<int:category_id>/", views.equipment_category_detail_view, name="equipment_category_detail"),

    # ✅ ремонт
    path("equipment/repairs/", views.repair_list_view, name="repair_list"),
    path("equipment/repairs/add/", views.repair_create_view, name="repair_add"),
    path("equipment/repairs/<int:repair_id>/close/", views.repair_close_view, name="repair_close"),
    path("equipment/repairs/<int:repair_id>/delete/", views.repair_delete_view, name="repair_delete"),

    # CRUD оборудования (только менеджер)
    path("equipment/add/", views.equipment_create_view, name="equipment_add"),
    path("equipment/<int:equipment_id>/edit/", views.equipment_update_view, name="equipment_edit"),
    path("equipment/<int:equipment_id>/delete/", views.equipment_delete_view, name="equipment_delete"),

    # CRUD категорий (только менеджер)
    path("equipment/categories/add/", views.category_create_view, name="category_add"),
    path("equipment/categories/<int:category_id>/edit/", views.category_update_view, name="category_edit"),
    path("equipment/categories/<int:category_id>/delete/", views.category_delete_view, name="category_delete"),


    # ---------- Склад (новая модель, этап 1) ----------
    path("warehouse/", views.stock_type_list_view, name="stock_type_list"),
    path("warehouse/repairs/", views.stock_repair_list_view, name="stock_repair_list"),

    # Категории/подкатегории склада
    path("warehouse/categories/", warehouse_views.stock_category_list_view, name="stock_category_list"),
    path("warehouse/categories/add/", warehouse_views.stock_category_add_view, name="stock_category_add"),
    path(
        "warehouse/categories/<int:category_id>/edit/",
        warehouse_views.stock_category_edit_view,
        name="stock_category_edit",
    ),
    path(
        "warehouse/categories/<int:category_id>/delete/",
        warehouse_views.stock_category_delete_view,
        name="stock_category_delete",
    ),
    path(
        "warehouse/categories/<int:category_id>/subcategories/",
        warehouse_views.stock_subcategory_list_view,
        name="stock_subcategory_list",
    ),
    path(
        "warehouse/categories/<int:category_id>/subcategories/add/",
        warehouse_views.stock_subcategory_add_view,
        name="stock_subcategory_add",
    ),
    path(
        "warehouse/subcategories/<int:subcategory_id>/edit/",
        warehouse_views.stock_subcategory_edit_view,
        name="stock_subcategory_edit",
    ),
    path(
        "warehouse/subcategories/<int:subcategory_id>/delete/",
        warehouse_views.stock_subcategory_delete_view,
        name="stock_subcategory_delete",
    ),
]
