from django import forms
from django.conf import settings

from inventory.models import Equipment
from .models import Event, EventEquipment, EventRentedEquipment

User = settings.AUTH_USER_MODEL


class EventForm(forms.ModelForm):
    """
    Форма создания/редактирования мероприятия.
    Работаем только с датами (без времени).
    end_date может быть пустой — тогда это однодневное мероприятие.
    """

    class Meta:
        model = Event
        fields = [
            "name",
            "start_date",
            "end_date",
            "client",
            "location",
            "responsible",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d"),
            "client": forms.TextInput(attrs={"class": "input"}),
            "location": forms.TextInput(attrs={"class": "input"}),
        }

    def init(self, *args, **kwargs):
        super().init(*args, **kwargs)

        # end_date необязателен (по ТЗ: если не указан — = start_date)
        self.fields["end_date"].required = False

        # чтобы формы корректно подхватывали initial для type="date"
        if self.instance and getattr(self.instance, "start_date", None):
            self.initial["start_date"] = self.instance.start_date
        if self.instance and getattr(self.instance, "end_date", None):
            self.initial["end_date"] = self.instance.end_date

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")

        # если конец не указан — считаем однодневным
        if start and not end:
            cleaned["end_date"] = start
            end = start

        if start and end and end < start:
            self.add_error("end_date", "Дата окончания не может быть раньше даты начала.")

        return cleaned


class EventEquipmentForm(forms.Form):
    equipment = forms.ModelChoiceField(
        queryset=Equipment.objects.all().order_by("name"),
        label="Оборудование",
    )
    quantity = forms.IntegerField(
        min_value=0,
        label="Количество",
        help_text="Если 0 — ничего не добавится.",
    )

    def init(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().init(*args, **kwargs)


class EventRentedEquipmentForm(forms.Form):
    equipment = forms.ModelChoiceField(
        queryset=Equipment.objects.all().order_by("name"),
        label="Оборудование (в аренду)",
    )
    quantity = forms.IntegerField(
        min_value=0,
        label="Количество",
        help_text="Если 0 — ничего не добавится.",
    )

    def init(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().init(*args, **kwargs)