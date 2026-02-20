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

    # stock reservations (phase 1)
    path("events/<int:event_id>/stock/add/", views.event_stock_add_view, name="event_stock_add"),
    path("events/<int:event_id>/stock/<int:reservation_id>/qty/", views.event_stock_update_qty_view, name="event_stock_update_qty"),
    path("events/<int:event_id>/stock/<int:reservation_id>/delete/", views.event_stock_delete_view, name="event_stock_delete"),

    # stock loading / scanning (phase 2)
    path("events/<int:event_id>/stock/load/", views.event_stock_load_view, name="event_stock_load"),
    path("events/<int:event_id>/stock/issue/<int:issue_id>/delete/", views.event_stock_issue_delete_view, name="event_stock_issue_delete"),

    # API
    path("api/events/quick-create/", views.quick_create_event_api, name="quick_create_event_api"),
    path("api/events/<int:event_id>/move/", views.quick_move_event_api, name="quick_move_event_api"),
]