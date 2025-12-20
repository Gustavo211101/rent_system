from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Event, EventEquipment


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'date_start',
        'date_end',
        'all_day',
        'client',
        'responsible',
        'open_in_site',
    )
    list_filter = ('all_day', 'date_start')
    search_fields = ('name', 'client', 'location')
    ordering = ('-date_start',)

    fieldsets = (
        (None, {
            'fields': ('name', 'all_day')
        }),
        ('Даты', {
            'fields': ('date_start', 'date_end')
        }),
        ('Дополнительно', {
            'fields': ('client', 'location', 'responsible')
        }),
    )

    def open_in_site(self, obj):
        url = reverse('event_detail', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank">Открыть</a>',
            url
        )

    open_in_site.short_description = 'Сайт'


@admin.register(EventEquipment)
class EventEquipmentAdmin(admin.ModelAdmin):
    list_display = ('event', 'equipment', 'quantity')
