from django.urls import path

from .views import (
    equipment_list_all_view,
    equipment_list_categories_view,
    equipment_detail_view,
)

urlpatterns = [
    path('equipment/', equipment_list_categories_view, name='equipment_list'),
    path('equipment/all/', equipment_list_all_view, name='equipment_list_all'),
    path('equipment/<int:equipment_id>/', equipment_detail_view, name='equipment_detail'),
]
