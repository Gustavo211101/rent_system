from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("api/list/", views.api_list, name="api_list"),
    path("api/mark-read/<int:notification_id>/", views.api_mark_read, name="api_mark_read"),
    path("api/mark-all-read/", views.api_mark_all_read, name="api_mark_all_read"),
    path("api/delete/<int:notification_id>/", views.api_delete, name="api_delete"),
]
