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
    list_display = ('name', 'start_date', 'end_date', 'status', 'responsible')
    list_filter = ('status', 'responsible')
    search_fields = ('name', 'client', 'location')
    ordering = ('-start_date',)
    inlines = [EventEquipmentInline, EventRentedEquipmentInline]


@admin.register(EventEquipment)
class EventEquipmentAdmin(admin.ModelAdmin):
    list_display = ('event', 'equipment', 'quantity')


@admin.register(EventRentedEquipment)
class EventRentedEquipmentAdmin(admin.ModelAdmin):
    list_display = ('event', 'equipment', 'quantity')
