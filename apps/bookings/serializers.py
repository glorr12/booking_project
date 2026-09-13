from rest_framework import serializers

from apps.bookings.models import Booking, BookingStatus
from apps.listings.models import Listing


class BookingSerializer(serializers.ModelSerializer):

    tenant = serializers.HiddenField(default=serializers.CurrentUserDefault())
    listing = serializers.PrimaryKeyRelatedField(queryset=Listing.objects.filter(is_active=True))
    listing_title = serializers.CharField(source='listing.title', read_only=True)

    class Meta:
        model = Booking
        fields = (
            'id', 'listing', 'listing_title', 'tenant', 'start_date', 'end_date',
            'status', 'created_at',
        )
        read_only_fields = ('id', 'status', 'created_at')

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        listing = attrs.get('listing', getattr(self.instance, 'listing', None))

        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError('End date must be after start date.')

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

        return attrs