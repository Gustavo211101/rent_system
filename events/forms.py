# events/forms.py
from django import forms

from .models import Event, EventEquipment, EventRentedEquipment
from inventory.models import Equipment


class EventForm(forms.ModelForm):
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
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class EventEquipmentForm(forms.ModelForm):
    """
    Форма добавления "своего" оборудования в мероприятие.
    Поддерживает параметр event=... (необязательный).
    """

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)  # важно: убираем event из kwargs
        super().__init__(*args, **kwargs)

        # базово показываем всё оборудование
        qs = Equipment.objects.all().order_by("name")

        # если захочешь позже фильтровать по доступности/категориям — делается тут
        # if event is not None:
        #     ...

        self.fields["equipment"].queryset = qs

        # quantity всегда >= 1
        self.fields["quantity"].min_value = 1
        self.fields["quantity"].initial = 1

    class Meta:
        model = EventEquipment
        fields = ["equipment", "quantity"]


class EventRentedEquipmentForm(forms.ModelForm):
    """
    Форма добавления "аренды" в мероприятие.
    Поддерживает параметр event=... (необязательный).
    """

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)  # важно: убираем event из kwargs
        super().__init__(*args, **kwargs)

        qs = Equipment.objects.all().order_by("name")
        self.fields["equipment"].queryset = qs

        self.fields["quantity"].min_value = 1
        self.fields["quantity"].initial = 1

    class Meta:
        model = EventRentedEquipment
        fields = ["equipment", "quantity"]
