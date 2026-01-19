from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect


def home(request):
    if request.user.is_authenticated:
        return redirect("calendar")
    return redirect("login")


urlpatterns = [
    path("", home),

    # apps
    path("", include("accounts.urls")),
    path("", include("events.urls")),
    path("", include("inventory.urls")),

    # journal
    path("audit/", include("audit.urls")),

    path("admin/", admin.site.urls),

    # cabinet
    path("cabinet/", include("cabinet.urls")),
]
