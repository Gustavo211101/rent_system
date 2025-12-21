from datetime import date, timedelta
import calendar

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

from accounts.permissions import user_can_edit
from inventory.models import Equipment
from .models import Event, EventEquipment, EventRentedEquipment
from .forms import EventForm, EventEquipmentForm, EventRentedEquipmentForm


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ
# =========================================================

def _can_modify_event(user, event: Event) -> bool:
    if user.is_superuser:
        return True
    if event.status == Event.STATUS_CLOSED:
        return False
    return user_can_edit(user)


def auto_close_past_events():
    today = date.today()
    Event.objects.filter(
        status__in=[
            Event.STATUS_DRAFT,
            Event.STATUS_CONFIRMED,
            Event.STATUS_IN_RENT,
        ],
        end_date__lt=today
    ).update(status=Event.STATUS_CLOSED)


def _event_reserved_other(event):
    qs = (
        EventEquipment.objects
        .filter(
            event__start_date__lte=event.end_date,
            event__end_date__gte=event.start_date
        )
        .exclude(event=event)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {r['equipment_id']: r['total'] or 0 for r in qs}


def _event_required(event):
    qs = (
        EventEquipment.objects
        .filter(event=event)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {r['equipment_id']: r['total'] or 0 for r in qs}


def _event_rented(event):
    qs = (
        EventRentedEquipment.objects
        .filter(event=event)
        .values('equipment_id')
        .annotate(total=Sum('quantity'))
    )
    return {r['equipment_id']: r['total'] or 0 for r in qs}


def _event_shortages(event):
    reserved_other = _event_reserved_other(event)
    required = _event_required(event)
    rented = _event_rented(event)

    result = []
    equipment = Equipment.objects.filter(id__in=required.keys())

    for eq in equipment:
        need = required.get(eq.id, 0)
        rented_qty = rented.get(eq.id, 0)
        used_other = reserved_other.get(eq.id, 0)

        available_own = max(eq.quantity_total - used_other, 0)
        effective = available_own + rented_qty
        shortage = max(need - effective, 0)

        if shortage > 0:
            result.append({
                'equipment': eq,
                'required': need,
                'available_own': available_own,
                'rented': rented_qty,
                'shortage': shortage,
            })

    return result


# =========================================================
# КАЛЕНДАРЬ
# =========================================================

@login_required
def calendar_view(request):
    auto_close_past_events()

    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(year, month)

    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    events = Event.objects.filter(
        start_date__lte=month_end,
        end_date__gte=month_start
    )

    events_by_day = {}
    for ev in events:
        d = ev.start_date
        while d <= ev.end_date:
            events_by_day.setdefault(d, []).append(ev)
            d += timedelta(days=1)

    return render(request, 'events/calendar.html', {
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'month_days': month_days,
        'events_by_day': events_by_day,
        'can_edit': user_can_edit(request.user),
    })


# =========================================================
# СОБЫТИЯ
# =========================================================

@login_required
def event_list_view(request):
    auto_close_past_events()
    events = Event.objects.order_by('-start_date')
    return render(request, 'events/event_list.html', {
        'events': events,
        'can_edit': user_can_edit(request.user),
    })


@login_required
def event_detail_view(request, event_id):
    auto_close_past_events()
    event = get_object_or_404(Event, id=event_id)

    equipment_items = EventEquipment.objects.filter(event=event).select_related('equipment')
    rented_items = EventRentedEquipment.objects.filter(event=event).select_related('equipment')

    return render(request, 'events/event_detail.html', {
        'event': event,
        'equipment_items': equipment_items,
        'rented_items': rented_items,
        'shortages': _event_shortages(event),
        'can_edit': user_can_edit(request.user),
        'can_modify': _can_modify_event(request.user, event),
    })


@login_required
def event_create_view(request):
    if not user_can_edit(request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            if not event.responsible:
                event.responsible = request.user
            event.save()
            return redirect('event_detail', event.id)
    else:
        form = EventForm()

    return render(request, 'events/event_form.html', {'form': form})


@login_required
def event_update_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            return redirect('event_detail', event.id)
    else:
        form = EventForm(instance=event)

    return render(request, 'events/event_form.html', {'form': form})


@login_required
def event_set_status_view(request, event_id, status):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden()

    allowed = {s[0] for s in Event.STATUS_CHOICES}
    if status in allowed:
        event.status = status
        event.save(update_fields=['status'])

    return redirect('event_detail', event.id)


# =========================================================
# ОБОРУДОВАНИЕ
# =========================================================

@login_required
def event_equipment_add_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not _can_modify_event(request.user, event):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = EventEquipmentForm(request.POST, event=event)
        if form.is_valid():
            eq = form.cleaned_data['equipment']
            qty = form.cleaned_data['quantity']
            item, _ = EventEquipment.objects.get_or_create(event=event, equipment=eq)
            item.quantity += qty
            item.save()
            event.equipment_tbd = False
            event.save(update_fields=['equipment_tbd'])
            return redirect('event_detail', event.id)
    else:
        form = EventEquipmentForm(event=event)

    return render(request, 'events/event_equipment_add.html', {
        'event': event,
        'form': form,
    })


@login_required
def event_equipment_update_qty_view(request, event_id, item_id):
    item = get_object_or_404(EventEquipment, id=item_id, event_id=event_id)
    if request.method == 'POST':
        qty = int(request.POST.get('quantity', 0))
        if qty <= 0:
            item.delete()
        else:
            item.quantity = qty
            item.save()
    return redirect('event_detail', event_id)


@login_required
def event_equipment_delete_view(request, event_id, item_id):
    item = get_object_or_404(EventEquipment, id=item_id, event_id=event_id)
    item.delete()
    return redirect('event_detail', event_id)


@login_required
def event_mark_equipment_tbd_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    event.equipment_tbd = True
    event.save(update_fields=['equipment_tbd'])
    return redirect('event_detail', event_id)


# =========================================================
# АРЕНДА
# =========================================================

@login_required
def event_rented_add_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        form = EventRentedEquipmentForm(request.POST, event=event)
        if form.is_valid():
            eq = form.cleaned_data['equipment']
            qty = form.cleaned_data['quantity']
            item, _ = EventRentedEquipment.objects.get_or_create(event=event, equipment=eq)
            item.quantity += qty
            item.save()
            return redirect('event_detail', event.id)
    else:
        form = EventRentedEquipmentForm(event=event)

    return render(request, 'events/event_rented_add.html', {
        'event': event,
        'form': form,
    })


@login_required
def event_rented_update_qty_view(request, event_id, item_id):
    item = get_object_or_404(EventRentedEquipment, id=item_id, event_id=event_id)
    if request.method == 'POST':
        qty = int(request.POST.get('quantity', 0))
        if qty <= 0:
            item.delete()
        else:
            item.quantity = qty
            item.save()
    return redirect('event_detail', event_id)


@login_required
def event_rented_delete_view(request, event_id, item_id):
    item = get_object_or_404(EventRentedEquipment, id=item_id, event_id=event_id)
    item.delete()
    return redirect('event_detail', event_id)
