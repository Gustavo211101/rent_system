from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.roles import ROLE_ENGINEER, ROLE_MANAGER, ROLE_SENIOR_ENGINEER
from inventory.models import Equipment, StockEquipmentType

from .models import Event, EventEquipment, EventRentedEquipment, EventRoleSlot
from .models import EventStockReservation

User = get_user_model()


DATE_WIDGET_FORMAT = "%Y-%m-%d"


def user_label(user: User) -> str:
    full_name = (f"{user.first_name or ''} {user.last_name or ''}").strip()
    if full_name:
        return f"{full_name} ({user.username})"
    return user.username


def _extra_roles_qs():
    return Group.objects.exclude(
        name__in=[ROLE_MANAGER, ROLE_SENIOR_ENGINEER, ROLE_ENGINEER]
    ).order_by("name")


class EventForm(forms.ModelForm):
    """
    + extra_roles (checkboxes)
    + for each extra role: multi-select users
    """

    # ✅ Fix: DateField с правильным форматом для <input type="date">
    start_date = forms.DateField(
        widget=forms.DateInput(format=DATE_WIDGET_FORMAT, attrs={"type": "date"}),
        input_formats=[DATE_WIDGET_FORMAT],
        localize=False,
        label="Дата начала",
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(format=DATE_WIDGET_FORMAT, attrs={"type": "date"}),
        input_formats=[DATE_WIDGET_FORMAT],
        localize=False,
        label="Дата окончания",
    )

    extra_roles = forms.ModelMultipleChoiceField(
        queryset=_extra_roles_qs(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Дополнительные роли на мероприятие",
    )

    class Meta:
        model = Event
        fields = [
            "name",
            "start_date",
            "end_date",
            "client",
            "location",
            "responsible",
            "s_engineer",
            "engineers",
            "notes",
            "status",
            "extra_roles",
        ]
        widgets = {
            "engineers": forms.SelectMultiple(attrs={"size": 8}),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Важные заметки менеджера (видны в календаре и карточке)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # дефолтные роли
        self.fields["responsible"].queryset = (
            User.objects.filter(groups__name=ROLE_MANAGER).order_by("username").distinct()
        )
        self.fields["s_engineer"].queryset = (
            User.objects.filter(groups__name=ROLE_SENIOR_ENGINEER).order_by("username").distinct()
        )
        self.fields["engineers"].queryset = (
            User.objects.filter(groups__name=ROLE_ENGINEER).order_by("username").distinct()
        )

        self.fields["responsible"].label_from_instance = user_label
        self.fields["s_engineer"].label_from_instance = user_label
        self.fields["engineers"].label_from_instance = user_label

        # ✅ критично: чтобы при редактировании value всегда был YYYY-MM-DD
        self.fields["start_date"].widget.format = DATE_WIDGET_FORMAT
        self.fields["end_date"].widget.format = DATE_WIDGET_FORMAT

        # динамические поля по дополнительным ролям
        self._extra_role_fields = []  # список (role, field_name)

        roles = list(_extra_roles_qs())

        # initial: роли и пользователи, если редактирование
        existing_by_role_id = {}
        if self.instance and getattr(self.instance, "id", None):
            existing_slots = (
                EventRoleSlot.objects.filter(event=self.instance)
                .select_related("role")
                .prefetch_related("users")
            )
            existing_by_role_id = {s.role_id: s for s in existing_slots}
            self.initial["extra_roles"] = Group.objects.filter(id__in=list(existing_by_role_id.keys()))

        for role in roles:
            fname = f"role_users_{role.id}"
            users_qs = User.objects.filter(groups=role).order_by("username").distinct()

            self.fields[fname] = forms.ModelMultipleChoiceField(
                queryset=users_qs,
                required=False,
                widget=forms.SelectMultiple(attrs={"size": 6}),
                label=f"{role.name} (можно несколько)",
            )
            self.fields[fname].label_from_instance = user_label

            slot = existing_by_role_id.get(role.id)
            if slot:
                self.initial[fname] = slot.users.all()

            self._extra_role_fields.append((role, fname))

    @property
    def extra_role_fields(self):
        """Для шаблона: список (role, bound_field)."""
        return [(role, self[fname]) for role, fname in self._extra_role_fields]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")

        if start and not end:
            cleaned["end_date"] = start

        if start and end and end < start:
            raise forms.ValidationError("Дата окончания не может быть раньше даты начала.")

        return cleaned

    def save(self, commit=True):
        event = super().save(commit=commit)

        selected_roles = list(self.cleaned_data.get("extra_roles") or [])

        if not event.pk:
            return event

        selected_ids = {r.id for r in selected_roles}

        EventRoleSlot.objects.filter(event=event).exclude(role_id__in=selected_ids).delete()

        for role in selected_roles:
            slot, _ = EventRoleSlot.objects.get_or_create(event=event, role=role)
            users = self.cleaned_data.get(f"role_users_{role.id}") or []
            slot.users.set(users)

        return event


class EventEquipmentForm(forms.ModelForm):
    equipment = forms.ModelChoiceField(
        queryset=Equipment.objects.all().order_by("name"),
        label="Оборудование",
    )
    quantity = forms.IntegerField(min_value=1, label="Количество")

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        if event:
            self.instance.event = event

    class Meta:
        model = EventEquipment
        fields = ["equipment", "quantity"]


class EventRentedEquipmentForm(forms.ModelForm):
    equipment = forms.ModelChoiceField(
        queryset=Equipment.objects.all().order_by("name"),
        label="Оборудование (аренда)",
    )
    quantity = forms.IntegerField(min_value=1, label="Количество")

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        if event:
            self.instance.event = event

    class Meta:
        model = EventRentedEquipment
        fields = ["equipment", "quantity"]


class EventStockReservationForm(forms.ModelForm):
    equipment_type = forms.ModelChoiceField(
        queryset=StockEquipmentType.objects.filter(is_active=True).select_related("category", "subcategory").order_by(
            "category__name", "subcategory__name", "name"
        ),
        label="Тип оборудования (склад)",
    )
    quantity = forms.IntegerField(min_value=1, label="Количество (бронь)")

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        if event is not None:
            self.instance.event = event

    class Meta:
        model = EventStockReservation
        fields = ["equipment_type", "quantity"]