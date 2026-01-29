from django.urls import path, include
from django.contrib.auth import views as auth_views

from .register_views import employee_register_view

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

    # регистрация по одноразовой ссылке
    path("register/<str:token>/", employee_register_view, name="employee_register"),

    # Персонал
    path("staff/", include("accounts.staff_urls")),
]
