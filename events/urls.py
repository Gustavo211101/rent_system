from django.urls import path
from .views import calendar_view

urlpatterns = [
    path('calendar/', calendar_view, name='calendar'),
]
