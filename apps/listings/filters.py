import django_filters

from apps.listings.models import Listing

DEFAULT_FILTER_CURRENCY = 'EUR'


class ListingFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(method='filter_price_min')
    price_max = django_filters.NumberFilter(method='filter_price_max')
    price_currency = django_filters.CharFilter(method='filter_noop')
    rooms_count_min = django_filters.NumberFilter(field_name='rooms_count', lookup_expr='gte')
    rooms_count_max = django_filters.NumberFilter(field_name='rooms_count', lookup_expr='lte')
    check_in = django_filters.DateFilter(method='filter_by_availability')
    check_out = django_filters.DateFilter(method='filter_noop')

    class Meta:
        model = Listing
        fields = (
            'city', 'district', 'housing_type', 'rooms_count',
            'rooms_count_min', 'rooms_count_max',
            'price_min', 'price_max', 'price_currency',
            'check_in', 'check_out',
        )

    def filter_noop(self, queryset, name, value):
        return queryset

    def _price_currency(self):
        return self.data.get('price_currency') or DEFAULT_FILTER_CURRENCY

    def filter_price_min(self, queryset, name, value):
        return queryset.filter(price__gte=value, price_currency=self._price_currency())

    def filter_price_max(self, queryset, name, value):
        return queryset.filter(price__lte=value, price_currency=self._price_currency())

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