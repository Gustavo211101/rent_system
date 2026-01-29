from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0004_event_team_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
    ]
