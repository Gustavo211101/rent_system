from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

app_name = "cabinet"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("profile/", views.profile_edit, name="profile_edit"),

    # Смена пароля (встроенные views Django)
    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(template_name="cabinet/password_change_form.html"),
        name="password_change",
    ),
    path(
        "password/change/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name="cabinet/password_change_done.html"),
        name="password_change_done",
    ),
]
