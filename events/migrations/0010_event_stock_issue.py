from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0009_event_stock_reservation"),
        ("inventory", "007_stockrepair_close_note"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventStockIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_issues", to="events.event")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="event_issues", to="inventory.stockequipmentitem")),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_stock_items", to=settings.AUTH_USER_MODEL)),
                ("returned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="returned_stock_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-issued_at", "-id"],
            },
        ),
    ]