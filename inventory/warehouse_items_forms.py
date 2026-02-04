from __future__ import annotations

from django import forms

from .models import StockEquipmentItem


class StockEquipmentItemForm(forms.ModelForm):
    class Meta:
        model = StockEquipmentItem
        fields = ["inventory_number", "status", "comment", "photo"]
        widgets = {
            "comment": forms.TextInput(attrs={"placeholder": "Комментарий (опционально)"}),
        }
