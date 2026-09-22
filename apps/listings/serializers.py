from decimal import Decimal

from django.db.models import Avg
from djmoney.contrib.django_rest_framework import MoneyField
from rest_framework import serializers

from apps.listings.models import BlockedDateRange, Listing, ListingImage

_UNANNOTATED = object()


class ListingImageSerializer(serializers.ModelSerializer):
    """
    Сериализатор для работы с изображениями листингов.
    Обеспечивает валидацию принадлежности листинга текущему пользователю-владельцу при добавлении фото
    """
    class Meta:
        model = ListingImage
        fields = ('id', 'listing', 'image', 'order')
        read_only_fields = ('id',)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.image:
            data['image'] = instance.image.url
        return data

    def validate_listing(self, listing):
        """
        Проверяет, что текущий пользователь является владельцем листинга, к которому добавляется фото
        """
        request = self.context.get('request')
        if request and listing.owner_id != request.user.id:
            raise serializers.ValidationError('You can only add photos to your own listing.')
        return listing


class ListingSerializer(serializers.ModelSerializer):
    """
    Сериализатор для детального представления и управления листингами недвижимости.
    Автоматически подставляет текущего пользователя как владельца через HiddenField,
    вычисляет рейтинг и количество отзывов с поддержкой аннотаций для избежания N+1 запросов,
    а также валидирует права арендодателя
    """
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    owner_id = serializers.UUIDField(read_only=True)
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    price = MoneyField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    rooms_count = serializers.IntegerField(min_value=1)
    max_guests = serializers.IntegerField(min_value=1, default=1)

    class Meta:
        model = Listing
        fields = (
            'id', 'owner', 'owner_id', 'owner_name', 'title', 'description', 'city', 'district',
            'price', 'rooms_count', 'housing_type', 'is_active', 'max_guests', 'images',
            'average_rating', 'reviews_count', 'created_at',
        )
        read_only_fields = ('id', 'created_at')

    def get_average_rating(self, obj) -> float | None:
        """
        Вычисляет или возвращает предварительно аннотированный средний рейтинг листинга
        """
        value = getattr(obj, 'average_rating', _UNANNOTATED)
        if value is _UNANNOTATED:
            value = obj.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(value, 2) if value is not None else None

    def get_reviews_count(self, obj) -> int:
        """
        Возвращает количество отзывов (из аннотации или через прямой запрос к базе)
        """
        value = getattr(obj, 'reviews_count', _UNANNOTATED)
        if value is _UNANNOTATED:
            return obj.reviews.count()
        return value

    def validate(self, attrs):
        """
        Проверяет общие ограничения при создании/редактировании листинга (например, статус арендодателя)
        """
        request = self.context.get('request')
        if request and not request.user.is_landlord:
            raise serializers.ValidationError('Only landlords can create/edit listings')
        return attrs


class BlockedDateRangeSerializer(serializers.ModelSerializer):
    """
    Сериализатор для управления заблокированными диапазонами дат листинга.
    Обеспечивает валидацию прав владельца и корректность временных интервалов (дата окончания позже даты начала)
    """
    class Meta:
        model = BlockedDateRange
        fields = ('id', 'listing', 'start_date', 'end_date', 'reason', 'created_at')
        read_only_fields = ('id', 'created_at')

    def validate(self, attrs):
        """
        Проверяет права владельца листинга и корректность последовательности дат
        """
        request = self.context.get('request')
        listing = attrs.get('listing', getattr(self.instance, 'listing', None))
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))

        if request and listing and listing.owner_id != request.user.id:
            raise serializers.ValidationError('You can only block dates on your own listing.')

        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError('End date must be after start date.')

        return attrs