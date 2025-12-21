from django import forms
from django.core.exceptions import ValidationError

from .models import Event, EventEquipment, EventRentedEquipment
from inventory.models import Equipment


class EventForm(forms.ModelForm):
    """
    Мы работаем по датам (дни).
    end_date можно не указывать — тогда считается = start_date.
    """
    class Meta:
        model = Event
        fields = ['name', 'start_date', 'end_date', 'client', 'location', 'responsible', 'status']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')

        if start and not end:
            cleaned['end_date'] = start
            self.instance.end_date = start

        if start and end and end < start:
            raise ValidationError("Дата окончания не может быть раньше даты начала.")

        return cleaned


class EventEquipmentForm(forms.Form):
    equipment = forms.ModelChoiceField(queryset=Equipment.objects.none(), label="Оборудование")
    quantity = forms.IntegerField(label="Количество", min_value=0, required=False)

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields['equipment'].queryset = Equipment.objects.all().order_by('name')

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None:
            return 0
        return int(qty)


class EventRentedEquipmentForm(forms.Form):
    equipment = forms.ModelChoiceField(queryset=Equipment.objects.none(), label="Оборудование")
    quantity = forms.IntegerField(label="Количество", min_value=0, required=False)

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields['equipment'].queryset = Equipment.objects.all().order_by('name')

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None:
            return 0
        return int(qty)
