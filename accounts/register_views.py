from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import StaffInvite
from .forms import EmployeeRegistrationForm


@require_http_methods(["GET", "POST"])
def employee_register_view(request, token: str):
    invite = get_object_or_404(StaffInvite, token=token)

    if invite.is_used:
        return render(request, "accounts/employee_register_used.html")

    if request.method == "POST":
        form = EmployeeRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            invite.mark_used(user)
            messages.success(request, "Регистрация завершена. Теперь вы можете войти.")
            return redirect("login")
    else:
        form = EmployeeRegistrationForm()

    return render(request, "accounts/employee_register.html", {"form": form})
