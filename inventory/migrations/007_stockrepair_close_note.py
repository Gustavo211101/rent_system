from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0006_alter_stockequipmentitem_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockrepair",
            name="close_note",
            field=models.TextField(blank=True),
        ),
    ]