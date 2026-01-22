from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_alter_equipment_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="EquipmentRepair",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("in_repair", "В ремонте"), ("returned", "Возвращено")], default="in_repair", max_length=20)),
                ("start_date", models.DateField(default=django.utils.timezone.localdate)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("equipment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="repairs", to="inventory.equipment")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
