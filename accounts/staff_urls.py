from django.urls import path
from . import staff_views
from .staff_invite_views import staff_invite_link_view

urlpatterns = [
    # lists
    path("personnel/", staff_views.staff_users_view, name="staff_users"),
    path("personnel/", staff_views.staff_users_view, name="personnel"),

    path("personnel/roles/", staff_views.staff_roles_view, name="staff_roles"),
    path("personnel/roles/", staff_views.staff_roles_view, name="personnel_roles"),

    # ссылка для нового сотрудника
    path("personnel/invite-link/", staff_invite_link_view, name="staff_invite_link"),

    # users CRUD
    path("personnel/user/add/", staff_views.staff_user_add_view, name="staff_user_add"),
    path("personnel/user/add/", staff_views.staff_user_add_view, name="personnel_user_add"),

    path("personnel/user/<int:user_id>/edit/", staff_views.staff_user_edit_view, name="staff_user_edit"),
    path("personnel/user/<int:user_id>/edit/", staff_views.staff_user_edit_view, name="personnel_user_edit"),

    path("personnel/user/<int:user_id>/delete/", staff_views.staff_user_delete_view, name="staff_user_delete"),
    path("personnel/user/<int:user_id>/delete/", staff_views.staff_user_delete_view, name="personnel_user_delete"),

    # roles CRUD
    path("personnel/roles/add/", staff_views.staff_role_add_view, name="staff_role_add"),
    path("personnel/roles/add/", staff_views.staff_role_add_view, name="personnel_role_add"),

    path("personnel/roles/<int:group_id>/edit/", staff_views.staff_role_edit_view, name="staff_role_edit"),
    path("personnel/roles/<int:group_id>/edit/", staff_views.staff_role_edit_view, name="personnel_role_edit"),

    path("personnel/roles/<int:group_id>/delete/", staff_views.staff_role_delete_view, name="staff_role_delete"),
    path("personnel/roles/<int:group_id>/delete/", staff_views.staff_role_delete_view, name="personnel_role_delete"),
]
