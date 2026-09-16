from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.bookings.models import Booking


@admin.register(Booking)
class BookingAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'listing', 'tenant', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('listing__title', 'tenant__email')