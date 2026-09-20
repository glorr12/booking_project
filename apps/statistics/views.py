from django.db.models import Avg, Count
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.listings.models import Listing
from apps.statistics.models import SearchQuery
from apps.statistics.serializers import PopularListingSerializer, PopularSearchSerializer

POPULAR_LIMIT = 10


class PopularListingsView(APIView):
    """
    API-представление для получения списка самых популярных объектов недвижимости .
    Что реализовано:
    Доступно для всех пользователей (`AllowAny`).
    Оптимизировано под высокие нагрузки: предотвращает проблему N+1 через `select_related` и `prefetch_related`.
    Аннотирует кварисет количеством просмотров, средним рейтингом и общим числом отзывов.
    Ограничивает выдачу константой `POPULAR_LIMIT`.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=PopularListingSerializer(many=True))
    def get(self, request):
        """
        Возвращает отсортированный по популярности (просмотрам) список активных листингов
        """
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
        serializer = PopularListingSerializer(listings, many=True, context={'request': request})
        return Response(serializer.data)


class PopularSearchesView(APIView):
    """
    API-представление для получения трендов и самых частых поисковых запросов.
    Что реализовано:
    Доступно для всех пользователей.
    Группирует ключевые слова по частоте использования для построения аналитики трендов.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=PopularSearchSerializer(many=True))
    def get(self, request):
        """
        Возвращает топ популярных ключевых слов на основе истории поисковых запросов
        """
        top = (
            SearchQuery.objects.values('keyword')
            .annotate(count=Count('id'))
            .order_by('-count')[:POPULAR_LIMIT]
        )
        return Response(list(top))