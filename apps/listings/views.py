from django.db.models import Avg, Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.response import Response

from apps.listings.filters import ListingFilter
from apps.listings.models import BlockedDateRange, Listing, ListingImage
from apps.listings.serializers import BlockedDateRangeSerializer, ListingImageSerializer, ListingSerializer
from apps.statistics.models import ListingView, SearchQuery


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner_id == request.user.id


class IsListingOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.listing.owner_id == request.user.id


class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ListingFilter
    search_fields = ('title', 'description', 'city')
    ordering_fields = ('price', 'created_at', 'average_rating', 'reviews_count')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Listing.objects.none()

        qs = Listing.objects.select_related('owner').prefetch_related('images').annotate(
            average_rating=Avg('reviews__rating'),
            reviews_count=Count('reviews', distinct=True),
        ).order_by('-created_at')

        user = self.request.user
        if not user.is_authenticated:
            return qs.filter(is_active=True)

        visible_ids = Listing.objects.filter(
            Q(is_active=True) | Q(owner=user) | Q(bookings__tenant=user)
        ).values('pk')
        return qs.filter(pk__in=visible_ids)

    def list(self, request, *args, **kwargs):
        keyword = request.query_params.get('search')
        if keyword:
            SearchQuery.objects.create(
                keyword=keyword,
                user=request.user if request.user.is_authenticated else None,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        ListingView.objects.create(
            listing=instance,
            user=request.user if request.user.is_authenticated else None,
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ListingImageViewSet(viewsets.ModelViewSet):
    queryset = ListingImage.objects.select_related('listing')
    serializer_class = ListingImageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsListingOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('listing',)
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']


class BlockedDateRangeViewSet(viewsets.ModelViewSet):
    queryset = BlockedDateRange.objects.select_related('listing')
    serializer_class = BlockedDateRangeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsListingOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('listing',)
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']