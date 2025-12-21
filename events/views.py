from datetime import date, timedelta
import calendar

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from accounts.permissions import user_can_edit
from inventory.models import Equipment
from .models import Event, EventEquipment, EventRentedEquipment
from .forms import EventForm, EventEquipmentForm, EventRentedEquipmentForm


def auto_close_past_events():
    """
    Автозакрытие:
    если end_date < сегодня (то есть "на следующий день после прохождения мероприятия")
    -> переводим в CLOSED.
    """
    today = timezone.localdate()
    Event.objects.filter(
        status__in=[Event.STATUS_DRAFT, Event.STATUS_CONFIRMED, Event.STATUS_CANCELLED],
        end_date__lt=today
    ).update(status=Event.STATUS_CLOSED)


def _can_modify_event(user, event: Event) -> bool:
    if user.is_superuser:
        return True
    if event.status == Event.STATUS_CLOSED:
        return False
    return user_can_edit(user)


def _reserved_other_map(event: Event) -> dict:
    """
    Сколько занято этого оборудования в ДРУГИХ мероприятиях,
    пересекающихся по датам с текущим event.
    """
    reserved = (
        EventEquipment.objects
        .filter(
            event__start_date__lte=event.end_date,
            event__end_date__gte=event.start_date,
        )
        .exclude(event=event)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {row['equipment_id']: int(row['total'] or 0) for row in reserved}


def _required_map(event: Event) -> dict:
    required = (
        EventEquipment.objects
        .filter(event=event)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {row['equipment_id']: int(row['total'] or 0) for row in required}


def _rented_map(event: Event) -> dict:
    rented = (
        EventRentedEquipment.objects
        .filter(event=event)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {row['equipment_id']: int(row['total'] or 0) for row in rented}


def _event_shortages(event: Event) -> list:
    """
    Возвращает список нехваток по оборудованию с учетом:
    - своего количества на складе
    - занято в других мероприятиях
    - взято в аренду (покрывает нехватку)
    """
    required_map = _required_map(event)
    if not required_map:
        return []

    reserved_other = _reserved_other_map(event)
    rented_map = _rented_map(event)

    eqs = Equipment.objects.filter(id__in=required_map.keys()).order_by('name')
    res = []

    for eq in eqs:
        required = int(required_map.get(eq.id, 0))
        rented = int(rented_map.get(eq.id, 0))
        used_other = int(reserved_other.get(eq.id, 0))

        available_own = eq.quantity_total - used_other
        if available_own < 0:
            available_own = 0

        effective = available_own + rented
        shortage = required - effective

        if shortage > 0:
            res.append({
                'equipment': eq,
                'required': required,
                'available_own': available_own,
                'rented': rented,
                'shortage': shortage,
            })

    res.sort(key=lambda x: x['shortage'], reverse=True)
    return res


@login_required
def calendar_view(request):
    auto_close_past_events()

    today = timezone.localdate()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(year, month)

    month_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = date(year, month, last_day)

    # Берем события, которые пересекаются с месяцем
    events = Event.objects.filter(
        start_date__lte=month_end,
        end_date__gte=month_start,
    ).order_by('start_date', 'name')

    events_by_day = {}
    event_has_problem = {}

    for ev in events:
        # помечаем проблему (нехватка оборудования)
        event_has_problem[ev.id] = len(_event_shortages(ev)) > 0

        d = ev.start_date
        while d <= ev.end_date:
            events_by_day.setdefault(d, []).append(ev)
            d = d + timedelta(days=1)

    return render(request, 'events/calendar.html', {
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'month_days': month_days,
        'events_by_day': events_by_day,
        'event_has_problem': event_has_problem,
        'can_edit': user_can_edit(request.user),
    })


@login_required
def event_list_view(request):
    auto_close_past_events()

    events = Event.objects.order_by('-start_date', '-id')
    return render(request, 'events/event_list.html', {
        'events': events,
        'can_edit': user_can_edit(request.user),
    })


@login_required
def event_detail_view(request, event_id):
    auto_close_past_events()

    event = get_object_or_404(Event, id=event_id)

    equipment_items = (
        EventEquipment.objects
        .filter(event=event)
        .select_related('equipment')
        .order_by('equipment__name')
    )
    rented_items = (
        EventRentedEquipment.objects
        .filter(event=event)
        .select_related('equipment')
        .order_by('equipment__name')
    )

    shortages = _event_shortages(event)

    return render(request, 'events/event_detail.html', {
        'event': event,
        'equipment_items': equipment_items,
        'rented_items': rented_items,
        'shortages': shortages,
        'can_edit': user_can_edit(request.user),
        'can_modify': _can_modify_event(request.user, event),
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

            # если end_date пустая — делаем однодневным
            if not event.end_date:
                event.end_date = event.start_date

            event.save()
            return redirect('event_detail', event_id=event.id)
    else:
        form = EventForm()

    return render(request, 'events/event_form.html', {
        'form': form,
        'title': 'Создание мероприятия',
    })


@login_required
def event_update_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя редактировать это мероприятие')

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save(commit=False)
            if not event.end_date:
                event.end_date = event.start_date
            event.save()
            return redirect('event_detail', event_id=event.id)
    else:
        form = EventForm(instance=event)

    return render(request, 'events/event_form.html', {
        'form': form,
        'title': 'Редактирование мероприятия',
    })


@login_required
def event_set_status_view(request, event_id, status):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя менять статус')

    allowed = {s[0] for s in Event.STATUS_CHOICES}
    if status not in allowed:
        return redirect('event_detail', event_id=event.id)

    event.status = status
    event.save(update_fields=['status'])
    return redirect('event_detail', event_id=event.id)


@login_required
def event_equipment_add_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять оборудование у закрытого мероприятия')

    if request.method == 'POST':
        form = EventEquipmentForm(request.POST, event=event)
        if form.is_valid():
            eq = form.cleaned_data['equipment']
            qty = int(form.cleaned_data.get('quantity') or 0)

            # 0 или пусто -> ничего не добавляем
            if qty <= 0:
                return redirect('event_detail', event_id=event.id)

            item, created = EventEquipment.objects.get_or_create(
                event=event,
                equipment=eq,
                defaults={'quantity': qty},
            )
            if not created:
                item.quantity = int(item.quantity or 0) + qty
                item.save()

            return redirect('event_detail', event_id=event.id)
    else:
        form = EventEquipmentForm(event=event)

    equipment_items = (
        EventEquipment.objects
        .filter(event=event)
        .select_related('equipment')
        .order_by('equipment__name')
    )

    return render(request, 'events/event_equipment_add.html', {
        'event': event,
        'form': form,
        'equipment_items': equipment_items,
        'shortages': _event_shortages(event),
    })


@login_required
def event_equipment_update_qty_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять оборудование')

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method != 'POST':
        return redirect('event_detail', event_id=event.id)

    try:
        qty = int((request.POST.get('quantity') or '0').strip())
    except ValueError:
        qty = 0

    if qty <= 0:
        item.delete()
        return redirect('event_detail', event_id=event.id)

    item.quantity = qty
    item.save()
    return redirect('event_detail', event_id=event.id)


@login_required
def event_equipment_delete_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять оборудование')

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method == 'POST':
        item.delete()

    return redirect('event_detail', event_id=event.id)


@login_required
def event_rented_add_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять аренду')

    if request.method == 'POST':
        form = EventRentedEquipmentForm(request.POST, event=event)
        if form.is_valid():
            eq = form.cleaned_data['equipment']
            qty = int(form.cleaned_data.get('quantity') or 0)

            if qty <= 0:
                return redirect('event_detail', event_id=event.id)

            item, created = EventRentedEquipment.objects.get_or_create(
                event=event,
                equipment=eq,
                defaults={'quantity': qty},
            )
            if not created:
                item.quantity = int(item.quantity or 0) + qty
                item.save()

            return redirect('event_detail', event_id=event.id)
    else:
        form = EventRentedEquipmentForm(event=event)

    rented_items = (
        EventRentedEquipment.objects
        .filter(event=event)
        .select_related('equipment')
        .order_by('equipment__name')
    )

    return render(request, 'events/event_rented_add.html', {
        'event': event,
        'form': form,
        'rented_items': rented_items,
        'shortages': _event_shortages(event),
    })


@login_required
def event_rented_update_qty_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять аренду')

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method != 'POST':
        return redirect('event_detail', event_id=event.id)

    try:
        qty = int((request.POST.get('quantity') or '0').strip())
    except ValueError:
        qty = 0

    if qty <= 0:
        item.delete()
        return redirect('event_detail', event_id=event.id)

    item.quantity = qty
    item.save()
    return redirect('event_detail', event_id=event.id)


@login_required
def event_rented_delete_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять аренду')

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method == 'POST':
        item.delete()

    return redirect('event_detail', event_id=event.id)
