from django.core.validators import MaxValueValidator, MinValueValidator
from rest_framework import serializers

from apps.bookings.models import BookingStatus
from apps.reviews.models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """
    Сериализатор для создания и обновления отзывов.
    Что реализовано:
    Автоматически подставляет текущего пользователя как автора через `CurrentUserDefault`.
    Валидирует, что отзыв оставляет именно арендатор по завершенному бронированию.
    Проверяет отсутствие дубликатов отзывов для одного бронирования.
    Автоматически привязывает листинг на основе выбранного `booking`.
    """
    author = serializers.HiddenField(default=serializers.CurrentUserDefault())
    author_id = serializers.UUIDField(read_only=True)
    author_name = serializers.CharField(source='author.name', read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    rating = serializers.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    class Meta:
        model = Review
        fields = (
            'id', 'booking', 'listing', 'listing_title', 'author', 'author_id', 'author_name',
            'rating', 'text', 'created_at',
        )
        read_only_fields = ('id', 'listing', 'created_at')

    def validate(self, attrs):
        """
        Комплексная валидация  бронирования и отзыва.
        Проверяет:
            Принадлежность бронирования текущему пользователю.
            Статус бронирования (должен быть COMPLETED).
            Отсутствие существующего отзыва для данной брони.
            Автоматически проставляет листинг из бронирования
        """
        request = self.context.get('request')
        booking = attrs.get('booking', getattr(self.instance, 'booking', None))

        if request and booking.tenant_id != request.user.id:
            raise serializers.ValidationError('You can only review your own booking.')
        if booking.status != BookingStatus.COMPLETED:
            raise serializers.ValidationError('You can only review a completed booking.')
        if hasattr(booking, 'review') and booking.review.pk != getattr(self.instance, 'pk', None):
            raise serializers.ValidationError('This booking already has a review.')

        attrs['listing'] = booking.listing
        return attrs