from django import forms

from .models import StockEquipmentItem


class StockEquipmentItemForm(forms.ModelForm):
    class Meta:
        model = StockEquipmentItem
        fields = ["inventory_number", "status", "comment", "photo"]
        widgets = {
            "inventory_number": forms.TextInput(attrs={"style": "width:100%; padding:10px 12px; border:1px solid #d1d5db; border-radius:10px;"}),
            "status": forms.Select(attrs={"style": "width:100%; padding:10px 12px; border:1px solid #d1d5db; border-radius:10px;"}),
            "comment": forms.TextInput(attrs={"style": "width:100%; padding:10px 12px; border:1px solid #d1d5db; border-radius:10px;"}),
        }
