from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets

from apps.reviews.models import Review
from apps.reviews.serializers import ReviewSerializer


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Пользовательский класс разрешений для проверки авторства объекта.
    Разрешает безопасные методы (GET, HEAD, OPTIONS) для любых пользователей,
    но ограничивает изменение или удаление объекта строго его автором
    """

    def has_object_permission(self, request, view, obj):
        """
        Проверяет права доступа к конкретному экземпляру объекта
        """
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author_id == request.user.id


class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления отзывами пользователей о листингах.
    Что реализовано:
    Оптимизирует выборки данных через `select_related('listing', 'author')` для предотвращения N+1 запросов.
    Реализует многоуровневую защиту: чтение доступно всем, создание — авторизованным пользователям,
    а модификация/удаление — только авторам отзыва (`IsAuthorOrReadOnly`).
    Поддерживает фильтрацию отзывов по конкретному листингу
    """
    queryset = Review.objects.select_related('listing', 'author')
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('listing',)