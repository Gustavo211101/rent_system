from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0008_event_role_slots"),
        ("inventory", "007_stockrepair_close_note"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventStockReservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_stock_reservations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "equipment_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="event_reservations",
                        to="inventory.stockequipmenttype",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_reservations",
                        to="events.event",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "equipment_type__category__name",
                    "equipment_type__subcategory__name",
                    "equipment_type__name",
                    "id",
                ],
                "unique_together": {("event", "equipment_type")},
            },
        ),
    ]
