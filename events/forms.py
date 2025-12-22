from django import forms

from inventory.models import Equipment
from .models import Event, EventEquipment, EventRentedEquipment


class EventForm(forms.ModelForm):
    """
    Форма мероприятия только по датам (без времени).
    end_date можно не заполнять — тогда будет равна start_date.
    """
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Дата начала",
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Дата окончания",
    )

    class Meta:
        model = Event
        fields = ["name", "start_date", "end_date", "client", "location", "responsible"]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")

        if start and not end:
            cleaned["end_date"] = start
            end = start

        if start and end and end < start:
            self.add_error("end_date", "Дата окончания не может быть раньше даты начала.")

        return cleaned


class EventEquipmentForm(forms.ModelForm):
    """
    ВАЖНО: принимает event=... чтобы не падать в views.
    """
    class Meta:
        model = EventEquipment
        fields = ["equipment", "quantity"]

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)  # <-- ключевая строка (чинит ошибку)
        super().__init__(*args, **kwargs)

        self.fields["equipment"].queryset = Equipment.objects.all().order_by("name")
        self.fields["quantity"].min_value = 0
        self.fields["quantity"].initial = 1


class EventRentedEquipmentForm(forms.ModelForm):
    """
    Аналогично: принимает event=...
    """
    class Meta:
        model = EventRentedEquipment
        fields = ["equipment", "quantity"]

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)

        self.fields["equipment"].queryset = Equipment.objects.all().order_by("name")
        self.fields["quantity"].min_value = 0
        self.fields["quantity"].initial = 1