from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0011_event_stock_issue_constraints"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="eventstockissue",
            name="uniq_event_stock_issue_event_item",
        ),
        migrations.AddConstraint(
            model_name="eventstockissue",
            constraint=models.UniqueConstraint(
                fields=("event", "item"),
                condition=models.Q(returned_at__isnull=True),
                name="uniq_event_stock_issue_active_event_item",
            ),
        ),
    ]
