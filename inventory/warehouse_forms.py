from django import forms

# NOTE: this module is used only by warehouse (stock) category/subcategory UI.
# We import models with a small safety net because the project is currently
# migrating from the old "equipment" inventory to the new "warehouse" flow.
try:
    from .models import StockCategory, StockSubcategory
except Exception:  # pragma: no cover
    StockCategory = None
    StockSubcategory = None


class StockCategoryForm(forms.ModelForm):
    class Meta:
        model = StockCategory
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Например: Видео",
            }),
        }


class StockSubcategoryForm(forms.ModelForm):
    class Meta:
        model = StockSubcategory
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Например: Камеры",
            }),
        }

from django import forms


class StockImportForm(forms.Form):
    file = forms.FileField(label="Excel файл (.xlsx)")

    def clean_file(self):
        f = self.cleaned_data["file"]
        name = (getattr(f, "name", "") or "").lower()
        if not name.endswith(".xlsx"):
            raise forms.ValidationError("Нужен файл .xlsx")
        return f
