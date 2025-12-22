from django.urls import path
from .staff_views import (
    staff_users_view,
    staff_user_create_view,
    staff_user_update_view,
    staff_user_delete_view,
    staff_roles_view,
    staff_role_create_view,
    staff_role_update_view,
    staff_role_delete_view,
)

urlpatterns = [
    path('', staff_users_view, name='staff_users'),

    path('users/', staff_users_view, name='staff_users'),
    path('users/add/', staff_user_create_view, name='staff_user_add'),
    path('users/<int:user_id>/edit/', staff_user_update_view, name='staff_user_edit'),
    path('users/<int:user_id>/delete/', staff_user_delete_view, name='staff_user_delete'),

    path('roles/', staff_roles_view, name='staff_roles'),
    path('roles/add/', staff_role_create_view, name='staff_role_add'),
    path('roles/<int:group_id>/edit/', staff_role_update_view, name='staff_role_edit'),
    path('roles/<int:group_id>/delete/', staff_role_delete_view, name='staff_role_delete'),
]