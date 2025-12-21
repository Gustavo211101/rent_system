from django.contrib import admin

from .models import Event, EventEquipment, EventRentedEquipment


class EventEquipmentInline(admin.TabularInline):
    model = EventEquipment
    extra = 0


class EventRentedEquipmentInline(admin.TabularInline):
    model = EventRentedEquipment
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'start_date',
        'end_date',
        'status',
        'responsible',
#        'equipment_tbd',
    )
    list_filter = ('status', 'equipment_tbd', 'responsible')
    search_fields = ('name', 'client', 'location')
    ordering = ('-start_date',)

    inlines = [EventEquipmentInline, EventRentedEquipmentInline]

    fieldsets = (
        (None, {
            'fields': (
                'name',
                ('start_date', 'end_date'),
                ('client', 'location'),
                'responsible',
                ('status'),
            )
        }),
    )


@admin.register(EventEquipment)
class EventEquipmentAdmin(admin.ModelAdmin):
    list_display = ('event', 'equipment', 'quantity')
    search_fields = ('event__name', 'equipment__name')


@admin.register(EventRentedEquipment)
class EventRentedEquipmentAdmin(admin.ModelAdmin):
    list_display = ('event', 'equipment', 'quantity')
    search_fields = ('event__name', 'equipment__name')
