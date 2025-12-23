# backend/urls.py

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views


def home(request):
    if request.user.is_authenticated:
        return redirect('calendar')
    return redirect('login')


urlpatterns = [
    path('', home),

    # apps
    path('', include('accounts.urls')),
    path('', include('events.urls')),
    path('', include('inventory.urls')),
    path('staff/', include('accounts.urls')),
    path('audit', include('audit.urls')),

    # logout нужен, потому что base.html ссылается на {% url 'logout' %}
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    path('admin/', admin.site.urls),
]