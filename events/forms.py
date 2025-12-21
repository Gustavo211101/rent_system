from django import forms
from django.utils import timezone

from .models import Event, EventEquipment, EventRentedEquipment


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'name',
            'start_date',
            'end_date',
            'client',
            'location',
            'responsible',
            'status',
            'equipment_tbd',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'Дата окончания не может быть раньше даты начала')

        return cleaned


class EventEquipmentForm(forms.ModelForm):
    class Meta:
        model = EventEquipment
        fields = ['equipment', 'quantity']

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        qty = cleaned.get('quantity') or 0
        eq = cleaned.get('equipment')

        if qty <= 0:
            self.add_error('quantity', 'Количество должно быть больше 0')
            return cleaned

        if self.event and eq:
            available = eq.available_quantity(self.event.start_date, self.event.end_date)
            if qty > available:
                # тут мы не запрещаем добавлять больше (как ты хотел ранее),
                # но если хочешь запрет — скажи, поменяем на add_error.
                pass

        return cleaned


class EventRentedEquipmentForm(forms.ModelForm):
    class Meta:
        model = EventRentedEquipment
        fields = ['equipment', 'quantity']

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        qty = cleaned.get('quantity') or 0
        if qty <= 0:
            self.add_error('quantity', 'Количество должно быть больше 0')
        return cleaned
