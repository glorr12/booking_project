import django_filters

from apps.listings.models import Listing


class ListingFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    rooms_count_min = django_filters.NumberFilter(field_name='rooms_count', lookup_expr='gte')
    rooms_count_max = django_filters.NumberFilter(field_name='rooms_count', lookup_expr='lte')
    check_in = django_filters.DateFilter(method='filter_by_availability')

    class Meta:
        model = Listing
        fields = (
            'city', 'district', 'housing_type', 'rooms_count',
            'rooms_count_min', 'rooms_count_max', 'price_min', 'price_max', 'check_in',
        )

    def filter_by_availability(self, queryset, name, value):
        check_out = self.data.get('check_out')
        if not check_out:
            return queryset

        from apps.bookings.models import BookingStatus
        return queryset.exclude(
            bookings__status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED],
            bookings__start_date__lt=check_out,
            bookings__end_date__gt=value,
        ).exclude(
            blocked_dates__start_date__lt=check_out,
            blocked_dates__end_date__gt=value,
        ).distinct()