from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(SimpleHistoryAdmin):
    list_display = ('listing', 'author', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('listing__title', 'author__email')