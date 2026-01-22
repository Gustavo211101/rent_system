from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0004_event_team_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="event",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
