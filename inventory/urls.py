from django.urls import path
from .views import (
    equipment_list_view,
    equipment_detail_view,
    equipment_create_view,
    equipment_update_view,
)

urlpatterns = [
    path('equipment/', equipment_list_view, name='equipment_list'),
    path('equipment/create/', equipment_create_view, name='equipment_create'),
    path('equipment/<int:equipment_id>/', equipment_detail_view, name='equipment_detail'),
    path('equipment/<int:equipment_id>/edit/', equipment_update_view, name='equipment_edit'),
]
