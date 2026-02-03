from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_equipmentrepair"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StockCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "verbose_name": "Категория склада",
                "verbose_name_plural": "Категории склада",
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="StockSubcategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subcategories", to="inventory.stockcategory")),
            ],
            options={
                "verbose_name": "Подкатегория склада",
                "verbose_name_plural": "Подкатегории склада",
                "ordering": ["category__name", "name", "id"],
                "unique_together": {("category", "name")},
            },
        ),
        migrations.CreateModel(
            name="StockEquipmentType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("weight_kg", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
                ("width_mm", models.PositiveIntegerField(blank=True, null=True)),
                ("height_mm", models.PositiveIntegerField(blank=True, null=True)),
                ("depth_mm", models.PositiveIntegerField(blank=True, null=True)),
                ("power_watt", models.PositiveIntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="equipment_types", to="inventory.stockcategory")),
                ("subcategory", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="equipment_types", to="inventory.stocksubcategory")),
            ],
            options={
                "verbose_name": "Тип оборудования склада",
                "verbose_name_plural": "Типы оборудования склада",
                "ordering": ["category__name", "subcategory__name", "name", "id"],
                "unique_together": {("category", "subcategory", "name")},
            },
        ),
        migrations.CreateModel(
            name="StockEquipmentItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("inventory_number", models.CharField(max_length=64, unique=True)),
                ("status", models.CharField(choices=[("storage", "На складе"), ("event", "На мероприятии"), ("repair", "В ремонте"), ("lost", "Утеряно")], default="storage", max_length=16)),
                ("comment", models.CharField(blank=True, max_length=255)),
                ("photo", models.FileField(blank=True, null=True, upload_to="equipment_photos/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("equipment_type", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="inventory.stockequipmenttype")),
            ],
            options={
                "verbose_name": "Единица оборудования",
                "verbose_name_plural": "Единицы оборудования",
                "ordering": ["equipment_type__name", "inventory_number", "id"],
            },
        ),
        migrations.CreateModel(
            name="StockRepair",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.TextField()),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="closed_stock_repairs", to=settings.AUTH_USER_MODEL)),
                ("opened_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opened_stock_repairs", to=settings.AUTH_USER_MODEL)),
                ("equipment_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="repairs", to="inventory.stockequipmentitem")),
            ],
            options={
                "verbose_name": "Ремонт (склад)",
                "verbose_name_plural": "Ремонты (склад)",
                "ordering": ["-opened_at", "-id"],
            },
        ),
    ]
