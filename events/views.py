from datetime import date
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
    Автозакрытие мероприятий:
    если date_end < текущего момента — переводим в closed.
    Запускаем в ключевых view (календарь/список/карточка).
    """
    now = timezone.now()
    Event.objects.filter(
        status__in=[Event.STATUS_DRAFT, Event.STATUS_CONFIRMED, Event.STATUS_IN_RENT],
        date_end__lt=now
    ).update(status=Event.STATUS_CLOSED)


def _can_modify_event(user, event: Event) -> bool:
    """
    Можно ли изменять мероприятие и связанные данные.
    - superuser: можно всегда
    - остальные: нельзя если закрыто
    - иначе: по ролям через user_can_edit
    """
    if user.is_superuser:
        return True
    if getattr(event, 'is_closed', False):
        return False
    return user_can_edit(user)


def _event_reserved_other_map(event: Event) -> dict:
    reserved = (
        EventEquipment.objects
        .filter(event__date_start__lt=event.date_end, event__date_end__gt=event.date_start)
        .exclude(event=event)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {row['equipment_id']: (row['total'] or 0) for row in reserved}


def _event_required_map(event: Event) -> dict:
    required = (
        EventEquipment.objects
        .filter(event=event)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {row['equipment_id']: (row['total'] or 0) for row in required}


def _event_rented_map(event: Event) -> dict:
    rented = (
        EventRentedEquipment.objects
        .filter(event=event)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {row['equipment_id']: (row['total'] or 0) for row in rented}


def _event_shortages(event: Event) -> list:
    reserved_other = _event_reserved_other_map(event)
    required_map = _event_required_map(event)
    rented_map = _event_rented_map(event)

    if not required_map:
        return []

    equipment_objs = Equipment.objects.filter(id__in=required_map.keys())
    result = []

    for eq in equipment_objs:
        required = int(required_map.get(eq.id, 0) or 0)
        rented = int(rented_map.get(eq.id, 0) or 0)

        used_other = int(reserved_other.get(eq.id, 0) or 0)
        available_own = eq.quantity_total - used_other
        if available_own < 0:
            available_own = 0

        effective = available_own + rented
        shortage = required - effective
        if shortage < 0:
            shortage = 0

        if shortage > 0:
            result.append({
                'equipment': eq,
                'required': required,
                'available_own': available_own,
                'rented': rented,
                'shortage': shortage,
            })

    result.sort(key=lambda x: x['shortage'], reverse=True)
    return result


@login_required
def calendar_view(request):
    auto_close_past_events()

    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(year, month)

    events = Event.objects.filter(date_start__year=year, date_start__month=month)

    events_by_day = {}
    for ev in events:
        day = ev.date_start.date()
        events_by_day.setdefault(day, []).append(ev)

    return render(request, 'events/calendar.html', {
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'month_days': month_days,
        'events_by_day': events_by_day,
        'can_edit': user_can_edit(request.user),
    })


@login_required
def event_list_view(request):
    auto_close_past_events()

    events = Event.objects.order_by('-date_start')
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

    can_edit = user_can_edit(request.user)
    can_modify = _can_modify_event(request.user, event)

    return render(request, 'events/event_detail.html', {
        'event': event,
        'equipment_items': equipment_items,
        'rented_items': rented_items,
        'shortages': shortages,
        'can_edit': can_edit,
        'can_modify': can_modify,
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
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя редактировать это мероприятие')

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
def event_set_status_view(request, event_id, status):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя менять статус этого мероприятия')

    allowed_statuses = {s[0] for s in Event.STATUS_CHOICES}
    if status not in allowed_statuses:
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

            if qty <= 0:
                return redirect('event_detail', event_id=event.id)

            try:
                item = EventEquipment.objects.get(event=event, equipment=eq)
                item.quantity = item.quantity + qty
                item.save()
            except EventEquipment.DoesNotExist:
                EventEquipment.objects.create(event=event, equipment=eq, quantity=qty)

            if event.equipment_tbd:
                event.equipment_tbd = False
                event.save(update_fields=['equipment_tbd'])

            return redirect('event_detail', event_id=event.id)
    else:
        form = EventEquipmentForm(event=event)

    equipment_items = (
        EventEquipment.objects
        .filter(event=event)
        .select_related('equipment')
        .order_by('equipment__name')
    )
    shortages = _event_shortages(event)

    return render(request, 'events/event_equipment_add.html', {
        'event': event,
        'form': form,
        'equipment_items': equipment_items,
        'shortages': shortages,
    })


@login_required
def event_equipment_update_qty_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять оборудование у закрытого мероприятия')

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method != 'POST':
        return redirect('event_detail', event_id=event.id)

    qty_raw = (request.POST.get('quantity') or '').strip()
    try:
        qty = int(qty_raw)
    except ValueError:
        return redirect('event_detail', event_id=event.id)

    if qty <= 0:
        item.delete()
        if not EventEquipment.objects.filter(event=event).exists():
            event.equipment_tbd = True
            event.save(update_fields=['equipment_tbd'])
        return redirect('event_detail', event_id=event.id)

    item.quantity = qty
    item.save()

    if event.equipment_tbd:
        event.equipment_tbd = False
        event.save(update_fields=['equipment_tbd'])

    return redirect('event_detail', event_id=event.id)


@login_required
def event_equipment_delete_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять оборудование у закрытого мероприятия')

    item = get_object_or_404(EventEquipment, id=item_id, event=event)

    if request.method == 'POST':
        item.delete()
        if not EventEquipment.objects.filter(event=event).exists():
            event.equipment_tbd = True
            event.save(update_fields=['equipment_tbd'])

    return redirect('event_detail', event_id=event.id)


@login_required
def event_mark_equipment_tbd_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя менять закрытое мероприятие')

    if request.method == 'POST':
        event.equipment_tbd = True
        event.save(update_fields=['equipment_tbd'])

    return redirect('event_detail', event_id=event.id)


@login_required
def event_rented_add_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять аренду у закрытого мероприятия')

    if request.method == 'POST':
        form = EventRentedEquipmentForm(request.POST, event=event)
        if form.is_valid():
            eq = form.cleaned_data['equipment']
            qty = int(form.cleaned_data.get('quantity') or 0)

            if qty <= 0:
                return redirect('event_detail', event_id=event.id)

            try:
                item = EventRentedEquipment.objects.get(event=event, equipment=eq)
                item.quantity = item.quantity + qty
                item.save()
            except EventRentedEquipment.DoesNotExist:
                EventRentedEquipment.objects.create(event=event, equipment=eq, quantity=qty)

            return redirect('event_detail', event_id=event.id)
    else:
        form = EventRentedEquipmentForm(event=event)

    rented_items = (
        EventRentedEquipment.objects
        .filter(event=event)
        .select_related('equipment')
        .order_by('equipment__name')
    )
    shortages = _event_shortages(event)

    return render(request, 'events/event_rented_add.html', {
        'event': event,
        'form': form,
        'rented_items': rented_items,
        'shortages': shortages,
    })


@login_required
def event_rented_update_qty_view(request, event_id, item_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя изменять аренду у закрытого мероприятия')

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method != 'POST':
        return redirect('event_detail', event_id=event.id)

    qty_raw = (request.POST.get('quantity') or '').strip()
    try:
        qty = int(qty_raw)
    except ValueError:
        return redirect('event_detail', event_id=event.id)

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
        return HttpResponseForbidden('Нельзя изменять аренду у закрытого мероприятия')

    item = get_object_or_404(EventRentedEquipment, id=item_id, event=event)

    if request.method == 'POST':
        item.delete()

    return redirect('event_detail', event_id=event.id)

@login_required
def event_set_status_view(request, event_id, status):
    event = get_object_or_404(Event, id=event_id)

    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden('Нельзя менять статус этого мероприятия')

    allowed_statuses = {s[0] for s in Event.STATUS_CHOICES}
    if status not in allowed_statuses:
        return redirect('event_detail', event_id=event.id)

    event.status = status
    event.save(update_fields=['status'])

    return redirect('event_detail', event_id=event.id)
