from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class ProfileForm(forms.ModelForm):
    """
    Редактирование профиля без смены пароля.
    """
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone"]
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "username"}),
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel"}),
        }

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Username обязателен.")
        qs = User.objects.filter(username=username).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Такой username уже занят.")
        return username

    def clean_email(self):
        # email у тебя, скорее всего, не уникальный — просто нормализуем
        return (self.cleaned_data.get("email") or "").strip()

    def clean_first_name(self):
        return (self.cleaned_data.get("first_name") or "").strip()

    def clean_last_name(self):
        return (self.cleaned_data.get("last_name") or "").strip()

    def clean_phone(self):
        return (self.cleaned_data.get("phone") or "").strip()
