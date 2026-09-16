from decimal import Decimal

from django.db.models import Avg
from djmoney.contrib.django_rest_framework import MoneyField
from rest_framework import serializers

from apps.listings.models import BlockedDateRange, Listing, ListingImage

_UNANNOTATED = object()


class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ('id', 'listing', 'image', 'order')
        read_only_fields = ('id',)

    def validate_listing(self, listing):
        request = self.context.get('request')
        if request and listing.owner_id != request.user.id:
            raise serializers.ValidationError('You can only add photos to your own listing.')
        return listing


class ListingSerializer(serializers.ModelSerializer):
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
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
            'id', 'owner', 'owner_name', 'title', 'description', 'city', 'district',
            'price', 'rooms_count', 'housing_type', 'is_active', 'max_guests', 'images',
            'average_rating', 'reviews_count', 'created_at',
        )
        read_only_fields = ('id', 'created_at')

    def get_average_rating(self, obj) -> float | None:
        value = getattr(obj, 'average_rating', _UNANNOTATED)
        if value is _UNANNOTATED:
            value = obj.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(value, 2) if value is not None else None

    def get_reviews_count(self, obj) -> int:
        value = getattr(obj, 'reviews_count', _UNANNOTATED)
        if value is _UNANNOTATED:
            return obj.reviews.count()
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        if request and not request.user.is_landlord:
            raise serializers.ValidationError('Only landlords can create/edit listings')
        return attrs


class BlockedDateRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedDateRange
        fields = ('id', 'listing', 'start_date', 'end_date', 'reason', 'created_at')
        read_only_fields = ('id', 'created_at')

    def validate(self, attrs):
        request = self.context.get('request')
        listing = attrs.get('listing', getattr(self.instance, 'listing', None))
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))

        if request and listing and listing.owner_id != request.user.id:
            raise serializers.ValidationError('You can only block dates on your own listing.')

        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError('End date must be after start date.')

        return attrs