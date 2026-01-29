from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

User = get_user_model()


class StaffUserForm(forms.ModelForm):
    """
    Пользователь для менеджера:

    - roles: множественный выбор ролей (groups) — то, что нам нужно
    - password1/password2: пароль задаём при создании, при редактировании можно оставить пустым
    """

    roles = forms.ModelMultipleChoiceField(
        label="Роли (можно несколько)",
        queryset=Group.objects.none(),  # ВАЖНО: заполним в __init__
        required=False,
    )

    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label="Повтор пароля", widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ гарантируем, что роли реально подгрузятся из БД
        self.fields["roles"].queryset = Group.objects.all().order_by("name")

        # выставим initial ролей при редактировании
        if self.instance and getattr(self.instance, "pk", None):
            self.fields["roles"].initial = list(self.instance.groups.all())

        # если phone вдруг отсутствует в модели — не ломаем форму
        if "phone" in self.fields and not hasattr(self.instance, "phone"):
            self.fields.pop("phone", None)

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Username обязателен.")
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Такой username уже занят.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1") or ""
        p2 = cleaned.get("password2") or ""

        is_new = not (self.instance and getattr(self.instance, "pk", None))

        if is_new:
            if not p1:
                raise ValidationError("Пароль обязателен для нового пользователя.")
            if p1 != p2:
                raise ValidationError("Пароли не совпадают.")
        else:
            # при редактировании пароль можно не менять
            if (p1 or p2) and p1 != p2:
                raise ValidationError("Пароли не совпадают.")

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)

        p1 = (self.cleaned_data.get("password1") or "").strip()
        if p1:
            user.set_password(p1)

        if commit:
            user.save()

            # ✅ сохраняем роли (groups) из чекбоксов
            selected_roles = list(self.cleaned_data.get("roles") or [])
            user.groups.set(selected_roles)

        return user


class StaffRoleForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]
