from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Логин / логаут
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='accounts/login.html'
        ),
        name='login'
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(
            next_page='login'
        ),
        name='logout'
    ),

    # "Персонал" (если уже сделал staff_urls.py)
    # ВАЖНО: staff_urls.py у тебя уже содержит префикс personnel/ (судя по скрину),
    # поэтому здесь подключаем без дополнительного префикса.
    path('', include('accounts.staff_urls')),
]