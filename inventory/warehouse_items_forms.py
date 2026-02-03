
from django import forms
from .models import StockEquipmentItem

class StockEquipmentItemForm(forms.ModelForm):
    class Meta:
        model = StockEquipmentItem
        fields = ["equipment_type", "inventory_number", "status", "comment", "photo"]
