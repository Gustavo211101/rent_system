from django import forms
from django.db.models import Sum

from .models import Event, EventEquipment, EventRentedEquipment
from inventory.models import Equipment


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'name',
            'status',
            'all_day',
#          'equipment_tbd',
            'date_start',
            'date_end',
            'client',
            'location',
            'responsible',
        ]
        widgets = {
            'date_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'date_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('date_start')
        end = cleaned_data.get('date_end')

        if start and end and end <= start:
            raise forms.ValidationError('Дата окончания должна быть позже даты начала')

        return cleaned_data


class EventEquipmentForm(forms.ModelForm):
    quantity = forms.IntegerField(min_value=0)

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        if self.event is not None:
            self.instance.event = self.event

            reserved = (
                EventEquipment.objects
                .filter(event__date_start__lt=self.event.date_end, event__date_end__gt=self.event.date_start)
                .exclude(event=self.event)
                .values('equipment_id')
                .annotate(total=Sum('quantity'))
            )
            reserved_map = {row['equipment_id']: row['total'] for row in reserved}

            self.fields['equipment'].queryset = Equipment.objects.select_related('category').order_by('category__name', 'name')

            def label_from_instance(obj):
                used_other = reserved_map.get(obj.id, 0) or 0
                available = obj.quantity_total - used_other
                if available < 0:
                    available = 0
                return f"{obj.name} — доступно: {available}"

            self.fields['equipment'].label_from_instance = label_from_instance

    class Meta:
        model = EventEquipment
        fields = ['equipment', 'quantity']


class EventRentedEquipmentForm(forms.ModelForm):
    quantity = forms.IntegerField(min_value=0)

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        if self.event is not None:
            self.instance.event = self.event
            self.fields['equipment'].queryset = Equipment.objects.select_related('category').order_by('category__name', 'name')

    class Meta:
        model = EventRentedEquipment
        fields = ['equipment', 'quantity']
