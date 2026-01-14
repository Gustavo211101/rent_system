from django.urls import path
from . import staff_views

urlpatterns = [
    # --- Users list (aliases) ---
    path("personnel/", staff_views.staff_users_view, name="personnel"),
    path("personnel/", staff_views.staff_users_view, name="staff_users"),  # алиас для шаблонов

    path("personnel/user/add/", staff_views.staff_user_add_view, name="personnel_user_add"),
    path("personnel/user/<int:user_id>/edit/", staff_views.staff_user_edit_view, name="personnel_user_edit"),
    path("personnel/user/<int:user_id>/delete/", staff_views.staff_user_delete_view, name="personnel_user_delete"),

    # --- Roles list (aliases) ---
    path("personnel/roles/", staff_views.staff_roles_view, name="personnel_roles"),
    path("personnel/roles/", staff_views.staff_roles_view, name="staff_roles"),  # алиас для шаблонов

    path("personnel/roles/add/", staff_views.staff_role_add_view, name="personnel_role_add"),
    path("personnel/roles/<int:group_id>/edit/", staff_views.staff_role_edit_view, name="personnel_role_edit"),
    path("personnel/roles/<int:group_id>/delete/", staff_views.staff_role_delete_view, name="personnel_role_delete"),
]
