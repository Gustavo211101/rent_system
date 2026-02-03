from django import forms

from .models import StockEquipmentType, StockCategory, StockSubcategory


class StockEquipmentTypeForm(forms.ModelForm):
    class Meta:
        model = StockEquipmentType
        fields = ["category", "subcategory", "name", "weight_kg", "dimensions_mm", "power_w"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "subcategory": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Наименование"}),
            "weight_kg": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Например: 1.25", "step": "0.01"}),
            "dimensions_mm": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например: 120×80×35"}),
            "power_w": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Например: 150", "step": "1"}),
        }
        

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # подкатегории необязательны
        self.fields["subcategory"].required = False
