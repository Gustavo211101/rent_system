from django import forms

from inventory.models import Equipment
from .models import Event, EventEquipment, EventRentedEquipment


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

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")

        # если дату окончания не указали — считаем однодневным
        if start and not end:
            cleaned["end_date"] = start

        if start and end and end < start:
            raise forms.ValidationError("Дата окончания не может быть раньше даты начала.")

        return cleaned


class EventEquipmentForm(forms.ModelForm):
    """
    ВАЖНО:
    - принимает event=... (kwargs)
    - проставляет instance.event ДО form.is_valid(), чтобы модельный clean() не падал
      (иначе и возникает RelatedObjectDoesNotExist: EventEquipment has no event)
    """
    equipment = forms.ModelChoiceField(
        queryset=Equipment.objects.all().order_by("name"),
        label="Оборудование",
    )
    quantity = forms.IntegerField(min_value=1, label="Количество")

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)

        # ✅ ключ: чтобы form.is_valid() не падал, если в модели clean() используется self.event
        if event is not None:
            self.instance.event = event

    class Meta:
        model = EventEquipment
        fields = ["equipment", "quantity"]


class EventRentedEquipmentForm(forms.ModelForm):
    """
    Аналогично: поддержка event=... и установка instance.event заранее.
    """
    equipment = forms.ModelChoiceField(
        queryset=Equipment.objects.all().order_by("name"),
        label="Оборудование (в аренду)",
    )
    quantity = forms.IntegerField(min_value=1, label="Количество")

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)

        if event is not None:
            self.instance.event = event

    class Meta:
        model = EventRentedEquipment
        fields = ["equipment", "quantity"]
