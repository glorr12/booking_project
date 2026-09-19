from datetime import date

from rest_framework import serializers

from apps.bookings.models import Booking, BookingStatus
from apps.listings.models import BlockedDateRange, Listing

MAX_BOOKING_DURATION_DAYS = 30


class BookingSerializer(serializers.ModelSerializer):
    """
    Сериалайзер для создания и изменения бронирования. Обрабатывает полезную нагрузку,
    добавляет снимок цены , а так же выполняет валидацию дат и пересечений броней
    """

    tenant = serializers.HiddenField(default=serializers.CurrentUserDefault())
    tenant_id = serializers.UUIDField(read_only=True)
    listing = serializers.PrimaryKeyRelatedField(queryset=Listing.objects.filter(is_active=True))
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    listing_owner_id = serializers.UUIDField(source='listing.owner_id', read_only=True)
    guests_count = serializers.IntegerField(min_value=1, default=1)

    class Meta:
        model = Booking
        fields = (
            'id', 'listing', 'listing_title', 'listing_owner_id', 'tenant', 'tenant_id',
            'start_date', 'end_date', 'guests_count', 'status', 'total_price', 'created_at',
        )
        read_only_fields = ('id', 'status', 'total_price', 'created_at')

    def _price_for(self, listing, start_date, end_date):
        """
        Рассчитывает общую стоимость бронирования на основе цены за ночь и длительности проживания
        """
        nights = (end_date - start_date).days
        return listing.price * nights

    def create(self, validated_data):
        """
        Создает объект бронирования, предварительно вычисляя и поставляя итоговую стоимость
        """
        validated_data['total_price'] = self._price_for(
            validated_data['listing'], validated_data['start_date'], validated_data['end_date'],
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Пересчитывает и обновляет стоимость букинга , если в передаваемых данных изменился листинг или диапазон дат
        """
        if {'listing', 'start_date', 'end_date'} & validated_data.keys():
            listing = validated_data.get('listing', instance.listing)
            start_date = validated_data.get('start_date', instance.start_date)
            end_date = validated_data.get('end_date', instance.end_date)
            validated_data['total_price'] = self._price_for(listing, start_date, end_date)
        return super().update(instance, validated_data)

    def validate(self, attrs):
        """
        Проверка дат , лимита длительности, числа гостей и предварительная проверка пересечений
        с активными бронями и с датами, которые перекрыты владельцем
        """
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        listing = attrs.get('listing', getattr(self.instance, 'listing', None))
        guests_count = attrs.get('guests_count', getattr(self.instance, 'guests_count', None))
        if self.instance and self.instance.status != BookingStatus.PENDING:
            terms_changed = (
                ('listing' in attrs and attrs['listing'].pk != self.instance.listing_id)
                or ('start_date' in attrs and attrs['start_date'] != self.instance.start_date)
                or ('end_date' in attrs and attrs['end_date'] != self.instance.end_date)
            )
            if terms_changed:
                raise serializers.ValidationError(
                    'Only a pending booking can have its dates or listing changed - '
                    'cancel and create a new booking instead.'
                )

        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError('End date must be after start date')

        if start_date and start_date < date.today():
            raise serializers.ValidationError('Start date must not be in the past')

        if start_date and end_date and (end_date - start_date).days > MAX_BOOKING_DURATION_DAYS:
            raise serializers.ValidationError(f'Bookings can be for at most {MAX_BOOKING_DURATION_DAYS} days')

        if listing and guests_count and guests_count > listing.max_guests:
            raise serializers.ValidationError(
                f'This listing sleeps at most {listing.max_guests} guest(s)'
            )

        if listing and start_date and end_date:
            overlapping = Booking.objects.filter(
                listing=listing,
                status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED],
                start_date__lt=end_date,
                end_date__gt=start_date,
            )
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise serializers.ValidationError('These dates are already booked')

            blocked = BlockedDateRange.objects.filter(
                listing=listing,
                start_date__lt=end_date,
                end_date__gt=start_date,
            )
            if blocked.exists():
                raise serializers.ValidationError('These dates are blocked by the listing owner')

        return attrs