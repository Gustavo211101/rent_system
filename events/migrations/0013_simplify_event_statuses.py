from __future__ import annotations

from datetime import date

from django.db import migrations, models


def forwards(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    EventStockIssue = apps.get_model("events", "EventStockIssue")

    today = date.today()

    # Map old statuses to new base statuses
    mapping = {
        "draft": "draft",
        "planned": "confirmed",
        "confirmed": "confirmed",
        "loading": "in_progress",
        "in_progress": "in_progress",
        "finished": "confirmed",
        "cancelled": "draft",
        "closed": "closed",
        "problem": "problem",
        "in_rent": "in_progress",
    }

    # First, remap unknown/legacy statuses into draft/confirmed/in_progress
    for old, new in mapping.items():
        Event.objects.filter(status=old).update(status=new)

    # Then, for past events apply auto close/problem
    past_qs = Event.objects.filter(end_date__lt=today, is_deleted=False)
    # Problem: any not-returned issues
    problem_ids = (
        EventStockIssue.objects.filter(returned_at__isnull=True, event__in=past_qs)
        .values_list("event_id", flat=True)
        .distinct()
    )
    past_qs.filter(id__in=problem_ids).update(status="problem")
    past_qs.exclude(id__in=problem_ids).update(status="closed")


def backwards(apps, schema_editor):
    # Irreversible (we don't restore legacy statuses)
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0012_event_stock_issue_active_event_item"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Черновик"),
                    ("confirmed", "Подтвержден"),
                    ("in_progress", "В работе"),
                    ("closed", "Закрыто"),
                    ("problem", "Проблема"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
