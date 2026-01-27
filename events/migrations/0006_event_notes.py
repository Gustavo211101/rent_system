from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0005_event_soft_delete"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
    ]
