from django.urls import path
from . import views

urlpatterns = [
    path("calendar/", views.calendar_view, name="calendar"),

    path("events/", views.event_list_view, name="event_list"),
    path("events/create/", views.event_create_view, name="event_create"),
    path("events/<int:event_id>/", views.event_detail_view, name="event_detail"),
    path("events/<int:event_id>/edit/", views.event_update_view, name="event_edit"),
    path("events/<int:event_id>/status/<str:status>/", views.event_set_status_view, name="event_set_status"),

    # soft delete / trash
    path("events/<int:event_id>/delete/", views.event_delete_view, name="event_delete"),
    path("events/trash/", views.event_trash_view, name="event_trash"),
    path("events/<int:event_id>/restore/", views.event_restore_view, name="event_restore"),
    path("events/<int:event_id>/purge/", views.event_purge_view, name="event_purge"),

    # equipment
    path("events/<int:event_id>/equipment/add/", views.event_equipment_add_view, name="event_equipment_add"),
    path("events/<int:event_id>/equipment/<int:item_id>/qty/", views.event_equipment_update_qty_view, name="event_equipment_update_qty"),
    path("events/<int:event_id>/equipment/<int:item_id>/delete/", views.event_equipment_delete_view, name="event_equipment_delete"),

    # rented
    path("events/<int:event_id>/rented/add/", views.event_rented_add_view, name="event_rented_add"),
    path("events/<int:event_id>/rented/<int:item_id>/qty/", views.event_rented_update_qty_view, name="event_rented_update_qty"),
    path("events/<int:event_id>/rented/<int:item_id>/delete/", views.event_rented_delete_view, name="event_rented_delete"),

    # stock reservations (phase 1)
    path("events/<int:event_id>/stock/add/", views.event_stock_add_view, name="event_stock_add"),
    path("events/<int:event_id>/stock/<int:reservation_id>/qty/", views.event_stock_update_qty_view, name="event_stock_update_qty"),
    path("events/<int:event_id>/stock/<int:reservation_id>/delete/", views.event_stock_delete_view, name="event_stock_delete"),

    # API
    path("api/events/quick-create/", views.quick_create_event_api, name="quick_create_event_api"),
    path("api/events/<int:event_id>/move/", views.quick_move_event_api, name="quick_move_event_api"),
]
