from django.urls import path
from . import views

urlpatterns = [
    # существующие страницы просмотра
    path("equipment/", views.equipment_list_all_view, name="equipment_list_all"),
    path("equipment/categories/", views.equipment_list_categories_view, name="equipment_list_categories"),
    path("equipment/category/<int:category_id>/", views.equipment_category_detail_view, name="equipment_category_detail"),

    # CRUD оборудования (только менеджер)
    path("equipment/add/", views.equipment_create_view, name="equipment_add"),
    path("equipment/<int:equipment_id>/edit/", views.equipment_update_view, name="equipment_edit"),
    path("equipment/<int:equipment_id>/delete/", views.equipment_delete_view, name="equipment_delete"),

    # CRUD категорий (только менеджер)
    path("equipment/categories/add/", views.category_create_view, name="category_add"),
    path("equipment/categories/<int:category_id>/edit/", views.category_update_view, name="category_edit"),
    path("equipment/categories/<int:category_id>/delete/", views.category_delete_view, name="category_delete"),
]