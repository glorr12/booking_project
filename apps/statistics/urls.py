from django.urls import path

from apps.statistics.views import PopularListingsView, PopularSearchesView

app_name = 'statistics'

urlpatterns = [
    path('popular-listings/', PopularListingsView.as_view(), name='popular-listings'),
    path('popular-searches/', PopularSearchesView.as_view(), name='popular-searches'),
]