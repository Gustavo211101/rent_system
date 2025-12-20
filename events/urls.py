from django.urls import path
from .views import (
    calendar_view,
    event_list_view,
)

urlpatterns = [
    path('calendar/', calendar_view, name='calendar'),
    path('events/', event_list_view, name='event_list'),
]
