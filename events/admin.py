from django.contrib import admin
from .models import Event, EventEquipment

class EventEquipmentInline(admin.TabularInline):
    model = EventEquipment
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    inlines = [EventEquipmentInline]
