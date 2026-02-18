from django import forms

from .models import StockEquipmentType, StockSubcategory


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

        # Показываем в выпадающем списке подкатегорий только те, что относятся
        # к выбранной категории.
        #
        # - Если категория ещё не выбрана — список подкатегорий пустой (чтобы не
        #   показывать "все подряд").
        # - При редактировании — подтягиваем подкатегории по категории объекта.
        category_id = None
        if self.data.get("category"):
            try:
                category_id = int(self.data.get("category"))
            except (TypeError, ValueError):
                category_id = None
        elif getattr(self.instance, "category_id", None):
            category_id = int(self.instance.category_id)

        if category_id:
            self.fields["subcategory"].queryset = (
                StockSubcategory.objects.filter(category_id=category_id).order_by("name")
            )
        else:
            self.fields["subcategory"].queryset = StockSubcategory.objects.none()

        # URL-основа для JS (см. шаблон), чтобы динамически подгружать
        # подкатегории при смене категории.
        self.fields["subcategory"].widget.attrs.setdefault(
            "data-subcategories-url", "/warehouse/subcategories/"
        )