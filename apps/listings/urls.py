from rest_framework.routers import DefaultRouter

from apps.listings.views import BlockedDateRangeViewSet, ListingImageViewSet, ListingViewSet

app_name = 'listings'

router = DefaultRouter()
router.register('images', ListingImageViewSet, basename='listing-image')
router.register('blocked-dates', BlockedDateRangeViewSet, basename='blocked-date-range')
router.register('', ListingViewSet, basename='listing')

urlpatterns = router.urls