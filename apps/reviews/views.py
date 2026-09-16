from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets

from apps.reviews.models import Review
from apps.reviews.serializers import ReviewSerializer


class IsAuthorOrReadOnly(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author_id == request.user.id


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related('listing', 'author')
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ('listing',)