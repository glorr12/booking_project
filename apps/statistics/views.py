from django.db.models import Avg, Count
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.listings.models import Listing
from apps.listings.serializers import ListingSerializer
from apps.statistics.models import SearchQuery
from apps.statistics.serializers import PopularListingSerializer, PopularSearchSerializer

POPULAR_LIMIT = 10


class PopularListingsView(APIView):

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=PopularListingSerializer(many=True))
    def get(self, request):
        listings = (
            Listing.objects.filter(is_active=True)
            .select_related('owner').prefetch_related('images')
            .annotate(
                views_count=Count('view_logs', distinct=True),
                average_rating=Avg('reviews__rating'),
                reviews_count=Count('reviews', distinct=True),
            )
            .order_by('-views_count')[:POPULAR_LIMIT]
        )
        serializer = ListingSerializer(listings, many=True, context={'request': request})
        data = serializer.data
        for item, listing in zip(data, listings):
            item['views_count'] = listing.views_count
        return Response(data)


class PopularSearchesView(APIView):

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=PopularSearchSerializer(many=True))
    def get(self, request):
        top = (
            SearchQuery.objects.values('keyword')
            .annotate(count=Count('id'))
            .order_by('-count')[:POPULAR_LIMIT]
        )
        return Response(list(top))