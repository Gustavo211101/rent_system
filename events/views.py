from datetime import date
import calendar

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

from accounts.permissions import user_can_edit
from .models import Event, EventEquipment
from .forms import EventForm, EventEquipmentForm


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
        'can_edit': user_can_edit(request.user),
    }

    return render(request, 'events/calendar.html', context)


@login_required
def event_list_view(request):
    events = Event.objects.order_by('-date_start')
    return render(request, 'events/event_list.html', {
        'events': events,
        'can_edit': user_can_edit(request.user),
    })


@login_required
def event_detail_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    equipment_items = EventEquipment.objects.filter(event=event).select_related('equipment')

    return render(request, 'events/event_detail.html', {
        'event': event,
        'equipment_items': equipment_items,
        'can_edit': user_can_edit(request.user),
    })


@login_required
def event_create_view(request):
    if not user_can_edit(request.user):
        return HttpResponseForbidden('Недостаточно прав')

    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            if not event.responsible:
                event.responsible = request.user
            event.save()

            if not event.equipment_tbd:
                return redirect('event_equipment_add', event_id=event.id)

            return redirect('event_detail', event_id=event.id)
    else:
        form = EventForm()

    return render(request, 'events/event_form.html', {
        'form': form,
        'title': 'Создание мероприятия',
    })


@login_required
def event_update_view(request, event_id):
    if not user_can_edit(request.user):
        return HttpResponseForbidden('Недостаточно прав')

    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            return redirect('event_detail', event_id=event.id)
    else:
        form = EventForm(instance=event)

    return render(request, 'events/event_form.html', {
        'form': form,
        'title': 'Редактирование мероприятия',
    })


@login_required
def event_equipment_add_view(request, event_id):
    if not user_can_edit(request.user):
        return HttpResponseForbidden('Недостаточно прав')

    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        form = EventEquipmentForm(request.POST, event=event)
        if form.is_valid():
            item = form.save(commit=False)
            item.event = event
            item.save()

            if event.equipment_tbd:
                event.equipment_tbd = False
                event.save(update_fields=['equipment_tbd'])

            return redirect('event_detail', event_id=event.id)
    else:
        form = EventEquipmentForm(event=event)

    equipment_items = EventEquipment.objects.filter(event=event).select_related('equipment')

    return render(request, 'events/event_equipment_add.html', {
        'event': event,
        'form': form,
        'equipment_items': equipment_items,
    })


@login_required
def event_equipment_delete_view(request, event_id, item_id):
    if not user_can_edit(request.user):
        return HttpResponseForbidden('Недостаточно прав')

    event = get_object_or_404(Event, id=event_id)
    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method == 'POST':
        item.delete()

        if not EventEquipment.objects.filter(event=event).exists():
            event.equipment_tbd = True
            event.save(update_fields=['equipment_tbd'])

        return redirect('event_detail', event_id=event.id)

    return redirect('event_detail', event_id=event.id)


@login_required
def event_mark_equipment_tbd_view(request, event_id):
    if not user_can_edit(request.user):
        return HttpResponseForbidden('Недостаточно прав')

    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        event.equipment_tbd = True
        event.save(update_fields=['equipment_tbd'])

    return redirect('event_detail', event_id=event.id)
