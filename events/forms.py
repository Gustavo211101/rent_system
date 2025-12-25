from django import forms
from .models import Event, EventEquipment, EventRentedEquipment
from inventory.models import Equipment


class EventForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d",
        ),
        label="Дата начала",
    )
    end_date = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d",
        ),
        label="Дата окончания",
        required=False,
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
        ]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")

        # если дату окончания не указали — считаем однодневным
        if start and not end:
            cleaned["end_date"] = start

        # защита от кривых дат
        if start and end and end < start:
            raise forms.ValidationError("Дата окончания не может быть раньше даты начала")

        return cleaned


class EventEquipmentForm(forms.ModelForm):
    class Meta:
        model = EventEquipment
        fields = ["equipment", "quantity"]


class EventRentedEquipmentForm(forms.ModelForm):
    class Meta:
        model = EventRentedEquipment
        fields = ["equipment", "quantity"]
