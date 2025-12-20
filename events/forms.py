from django import forms
from django.db.models import Sum

from .models import Event, EventEquipment
from inventory.models import Equipment


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'name',
            'all_day',
            'equipment_tbd',
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
    """
    Форма добавления оборудования в мероприятие.

    - event нужен ДО is_valid(), потому что EventEquipment.clean() использует self.event.
    - В dropdown показываем "Название — доступно: X".
    - В dropdown показываем только позиции с available > 0 (для дат события).
    """

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.event = event
        if self.event is not None:
            self.instance.event = self.event

            # Для дат события считаем сколько занято каждой позицией
            # (пересечение интервалов: start < end && end > start)
            reserved = (
                EventEquipment.objects
                .filter(
                    event__date_start__lt=self.event.date_end,
                    event__date_end__gt=self.event.date_start
                )
                .values('equipment_id')
                .annotate(total=Sum('quantity'))
            )
            reserved_map = {row['equipment_id']: row['total'] for row in reserved}

            # Список доступных ID (available > 0)
            available_ids = []
            for eq in Equipment.objects.all():
                used = reserved_map.get(eq.id, 0) or 0
                available = eq.quantity_total - used
                if available > 0:
                    available_ids.append(eq.id)

            self.fields['equipment'].queryset = Equipment.objects.filter(id__in=available_ids).order_by('name')

            # Красивые подписи: "Название — доступно: X"
            def label_from_instance(obj):
                used = reserved_map.get(obj.id, 0) or 0
                available = obj.quantity_total - used
                return f"{obj.name} — доступно: {available}"

            self.fields['equipment'].label_from_instance = label_from_instance

    class Meta:
        model = EventEquipment
        fields = ['equipment', 'quantity']
