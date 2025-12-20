from django.urls import path
from .views import (
    calendar_view,
    event_list_view,
    event_detail_view,
    event_create_view,
    event_update_view,
    event_equipment_add_view,
    event_equipment_delete_view,
    event_mark_equipment_tbd_view,
)

urlpatterns = [
    path('calendar/', calendar_view, name='calendar'),

    path('events/', event_list_view, name='event_list'),
    path('events/create/', event_create_view, name='event_create'),
    path('events/<int:event_id>/', event_detail_view, name='event_detail'),
    path('events/<int:event_id>/edit/', event_update_view, name='event_edit'),

    path('events/<int:event_id>/equipment/add/', event_equipment_add_view, name='event_equipment_add'),
    path('events/<int:event_id>/equipment/<int:item_id>/delete/', event_equipment_delete_view, name='event_equipment_delete'),
    path('events/<int:event_id>/equipment/tbd/', event_mark_equipment_tbd_view, name='event_equipment_tbd'),
]
