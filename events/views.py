from datetime import date
import calendar

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Event


@login_required
def calendar_view(request):
    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(year, month)

    events = Event.objects.filter(
        date_start__year=year,
        date_start__month=month
    )

    events_by_day = {}
    for event in events:
        day = event.date_start.date()
        events_by_day.setdefault(day, []).append(event)

    context = {
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'month_days': month_days,
        'events_by_day': events_by_day,
    }

    return render(request, 'events/calendar.html', context)

def event_list_view(request):
    events = Event.objects.order_by('-date_start')
    return render(request, 'events/event_list.html', {
        'events': events
    })