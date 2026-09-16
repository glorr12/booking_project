from django.contrib import admin

from apps.statistics.models import ListingView, SearchQuery


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'user', 'created_at')
    search_fields = ('keyword',)


@admin.register(ListingView)
class ListingViewAdmin(admin.ModelAdmin):
    list_display = ('listing', 'user', 'created_at')