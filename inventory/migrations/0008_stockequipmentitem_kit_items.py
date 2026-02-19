from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "007_stockrepair_close_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockequipmentitem",
            name="kit_items",
            field=models.ManyToManyField(
                blank=True,
                related_name="kit_parents",
                symmetrical=False,
                to="inventory.stockequipmentitem",
                verbose_name="Комплект",
            ),
        ),
    ]