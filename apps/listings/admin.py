from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.listings.models import BlockedDateRange, Listing, ListingImage


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1


@admin.register(Listing)
class ListingAdmin(SimpleHistoryAdmin):
    list_display = ('title', 'owner', 'city', 'price', 'housing_type', 'is_active', 'max_guests', 'created_at')
    list_filter = ('housing_type', 'is_active', 'city')
    search_fields = ('title', 'city', 'district')
    inlines = [ListingImageInline]


@admin.register(BlockedDateRange)
class BlockedDateRangeAdmin(admin.ModelAdmin):
    list_display = ('listing', 'start_date', 'end_date', 'reason', 'created_at')
    list_filter = ('start_date',)
    search_fields = ('listing__title', 'reason')