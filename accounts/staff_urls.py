from django.urls import path
from . import staff_views

urlpatterns = [
    # вкладка "Персонал"
    path("", staff_views.staff_users_view, name="personnel"),
    path("user/add/", staff_views.staff_user_add_view, name="personnel_user_add"),
    path("user/<int:user_id>/edit/", staff_views.staff_user_edit_view, name="personnel_user_edit"),
    path("user/<int:user_id>/delete/", staff_views.staff_user_delete_view, name="personnel_user_delete"),

    # вкладка "Роли"
    path("roles/", staff_views.staff_roles_view, name="personnel_roles"),
    path("roles/add/", staff_views.staff_role_add_view, name="personnel_role_add"),
    path("roles/<int:group_id>/edit/", staff_views.staff_role_edit_view, name="personnel_role_edit"),
    path("roles/<int:group_id>/delete/", staff_views.staff_role_delete_view, name="personnel_role_delete"),
]