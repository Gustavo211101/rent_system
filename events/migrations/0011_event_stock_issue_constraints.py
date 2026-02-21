from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0010_event_stock_issue"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="eventstockissue",
            constraint=models.UniqueConstraint(
                fields=("event", "item"),
                name="uniq_event_stock_issue_event_item",
            ),
        ),
        migrations.AddConstraint(
            model_name="eventstockissue",
            constraint=models.UniqueConstraint(
                fields=("item",),
                condition=models.Q(returned_at__isnull=True),
                name="uniq_event_stock_issue_active_item",
            ),
        ),
    ]
