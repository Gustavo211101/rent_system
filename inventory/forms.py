from django import forms
from .models import Equipment


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            'name',
            'category',
            'serial_number',
            'quantity_total',
            'location',
            'status',
            'notes',
        ]
