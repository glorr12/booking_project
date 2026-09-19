from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.bookings.models import Booking
from core.admin import SoftDeleteAdminMixin


@admin.register(Booking)
class BookingAdmin(SoftDeleteAdminMixin, SimpleHistoryAdmin):
    list_display = (
        'id', 'listing', 'tenant', 'start_date', 'end_date', 'status', 'is_deleted', 'created_at',
    )
    list_filter = ('status', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('listing__title', 'tenant__email')