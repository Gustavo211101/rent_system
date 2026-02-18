from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0007_merge_0005_event_soft_delete_0006_event_notes"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventRoleSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_slots", to="events.event")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="event_role_slots", to="auth.group")),
                ("users", models.ManyToManyField(blank=True, related_name="event_extra_roles", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["role__name", "id"],
                "unique_together": {("event", "role")},
            },
        ),
    ]