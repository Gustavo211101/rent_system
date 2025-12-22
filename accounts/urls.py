from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="login"),
        name="logout",
    ),

    # Персонал (менеджер)
    path("personnel/", include("accounts.staff_urls")),
]