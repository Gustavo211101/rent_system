from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0003_alter_event_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="s_engineer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="senior_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="engineers",
            field=models.ManyToManyField(
                blank=True,
                related_name="engineer_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
