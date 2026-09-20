from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, serializers, viewsets
from rest_framework.response import Response

from apps.listings.filters import ListingFilter
from apps.listings.models import BlockedDateRange, Listing, ListingImage
from apps.listings.serializers import BlockedDateRangeSerializer, ListingImageSerializer, ListingSerializer
from apps.statistics.models import ListingView, SearchQuery

VIEW_DEDUP_WINDOW_MINUTES = 30


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Кастомный класс разрешений для DRF

    Разрешает безопасные методы (GET, HEAD, OPTIONS) для любых пользователей,
    а операции изменения (POST, PUT, PATCH, DELETE) разрешает только владельцу объекта
    """
    def has_object_permission(self, request, view, obj):
        """
        Проверяет права доступа к конкретному экземпляру модели на уровне объекта
        """
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner_id == request.user.id


class IsListingOwnerOrReadOnly(permissions.BasePermission):
    """
    Кастомный класс разрешений  для DRF для сущностей, связанных с листингом

    Разрешает безопасные методы (GET, HEAD, OPTIONS) для всех пользователей,
    а операции модификации разрешает исключительно владельцу родительского листинга
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.listing.owner_id == request.user.id


class ListingViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления листингами недвижимости
    """
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ListingFilter
    search_fields = ('title', 'description', 'city')
    ordering_fields = ('price', 'created_at', 'average_rating', 'reviews_count')

    def get_queryset(self):
        """
        Формирует базовый оптимизированный QuerySet с учетом прав доступа и статуса авторизации
        """
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
        """
        Обрабатывает GET-запрос списка листингов. Логирует поисковый запрос, если передан параметр search
        """
        keyword = request.query_params.get('search')
        if keyword:
            SearchQuery.objects.create(
                keyword=keyword.strip().lower(),
                user=request.user if request.user.is_authenticated else None,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Обрабатывает GET-запрос детальной информации по листингу с защитой от накрутки просмотров
        """
        instance = self.get_object()
        user = request.user if request.user.is_authenticated else None
        is_owner_viewing = user is not None and user.id == instance.owner_id
        recently_viewed = user is not None and ListingView.objects.filter(
            listing=instance,
            user=user,
            created_at__gte=timezone.now() - timedelta(minutes=VIEW_DEDUP_WINDOW_MINUTES),
        ).exists()
        if not is_owner_viewing and not recently_viewed:
            ListingView.objects.create(listing=instance, user=user)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ListingImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления изображениями листингов.
    Разрешает операции чтения всем, а изменения только владельцу родительского листинга
    """
    queryset = ListingImage.objects.select_related('listing')
    serializer_class = ListingImageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsListingOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('listing',)
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']


class BlockedDateRangeViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления периодами заблокированных дат владельцем листинга.
    Реализует строгую защиту от параллельных бронирований и пересечений дат
    с помощью блокировки строк в БД
    """
    queryset = BlockedDateRange.objects.select_related('listing')
    serializer_class = BlockedDateRangeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsListingOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('listing',)
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def _lock_and_check_dates(self, listing, start_date, end_date, exclude_range_id=None):
        """
        Блокирует строку листинга в базе данных и проверяет отсутствие пересечений с активными бронями и блокировками
        """
        Listing.objects.select_for_update().get(pk=listing.pk)

        from apps.bookings.models import Booking, BookingStatus

        overlapping_bookings = Booking.objects.filter(
            listing=listing,
            status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED],
            start_date__lt=end_date,
            end_date__gt=start_date,
        )
        if overlapping_bookings.exists():
            raise serializers.ValidationError(
                {'non_field_errors': ['These dates already have a booking']}
            )

        overlapping_ranges = BlockedDateRange.objects.filter(
            listing=listing,
            start_date__lt=end_date,
            end_date__gt=start_date,
        )
        if exclude_range_id:
            overlapping_ranges = overlapping_ranges.exclude(pk=exclude_range_id)
        if overlapping_ranges.exists():
            raise serializers.ValidationError(
                {'non_field_errors': ['These dates are already blocked']}
            )

    def perform_create(self, serializer):
        """
        Создает заблокированный диапазон дат внутри атомарной транзакции с предварительной блокировкой
        """
        listing = serializer.validated_data['listing']
        start_date = serializer.validated_data['start_date']
        end_date = serializer.validated_data['end_date']

        with transaction.atomic():
            self._lock_and_check_dates(listing, start_date, end_date)
            serializer.save()

    def perform_update(self, serializer):
        """
        Обновляет заблокированный диапазон дат внутри атомарной транзакции с проверкой пересечений
        """
        instance = serializer.instance
        touches_dates = {'listing', 'start_date', 'end_date'} & serializer.validated_data.keys()
        if not touches_dates:
            serializer.save()
            return

        listing = serializer.validated_data.get('listing', instance.listing)
        start_date = serializer.validated_data.get('start_date', instance.start_date)
        end_date = serializer.validated_data.get('end_date', instance.end_date)

        with transaction.atomic():
            self._lock_and_check_dates(listing, start_date, end_date, exclude_range_id=instance.pk)
            serializer.save()