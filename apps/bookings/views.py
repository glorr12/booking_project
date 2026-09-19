from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.bookings.models import Booking, BookingStatus
from apps.bookings.serializers import BookingSerializer
from apps.listings.models import BlockedDateRange, Listing

CANCELLATION_DEADLINE_DAYS = 3


class IsTenantOrListingOwner(permissions.BasePermission):
    """
     Правила доступа на уровне объекта для отдельного бронирования.
    Оба участника могут просматривать бронирование, но только арендатор может изменять его условия через
    общие конечные точки обновления. единственные способы, которыми владелец может повлиять на бронирование — это специальные
    действия "confirm"/"reject"/"cancel-by-owner" приведенные ниже, которые выполняют собственную явную
    проверку прав владения. "update"/"partial_update" намеренно исключены из этого списка разрешенных действий
    если бы владельцу было разрешено использовать "PATCH" для бронирования арендатора, он мог бы незаметно изменить чужие
    даты или количество гостей вне рабочего процесса подтверждения/отклонения/отмены. Простое "DELETE" не
    указано ни для кого поскольку у «Booking» нет собственной функции «мягкого удаления»,
     поэтому жесткое удаление привело бы к каскадному удалению «Review» арендатора,
    вместо этого используются действия cancel/cancel-by-owner, которые просто меняют status
    """

    OBJECT_ACTIONS_OPEN_TO_OWNER = {'confirm', 'reject', 'cancel', 'cancel_by_owner'}

    def has_object_permission(self, request, view, obj):
        is_tenant = obj.tenant_id == request.user.id
        is_owner = obj.listing.owner_id == request.user.id

        if request.method in permissions.SAFE_METHODS:
            return is_tenant or is_owner

        if getattr(view, 'action', None) in self.OBJECT_ACTIONS_OPEN_TO_OWNER:
            return is_tenant or is_owner
        return is_tenant


class BookingViewSet(viewsets.ModelViewSet):
    """
    Обычный CRUD , кроме "PUT" "DELETE"
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantOrListingOwner]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        user = self.request.user
        return (
            Booking.objects.filter(Q(tenant=user) | Q(listing__owner=user))
            .select_related('listing', 'tenant')
        )

    def _lock_and_check_dates(self, listing, start_date, end_date, exclude_booking_id=None):
        Listing.objects.select_for_update().get(pk=listing.pk)

        still_overlapping = Booking.objects.filter(
            listing=listing,
            status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED],
            start_date__lt=end_date,
            end_date__gt=start_date,
        )
        if exclude_booking_id:
            still_overlapping = still_overlapping.exclude(pk=exclude_booking_id)
        if still_overlapping.exists():
            raise serializers.ValidationError({'non_field_errors': ['These dates are already booked']})

        still_blocked = BlockedDateRange.objects.filter(
            listing=listing,
            start_date__lt=end_date,
            end_date__gt=start_date,
        )
        if still_blocked.exists():
            raise serializers.ValidationError(
                {'non_field_errors': ['These dates are blocked by the listing owner']}
            )

    def perform_create(self, serializer):
        listing = serializer.validated_data['listing']
        start_date = serializer.validated_data['start_date']
        end_date = serializer.validated_data['end_date']

        with transaction.atomic():
            self._lock_and_check_dates(listing, start_date, end_date)
            serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        touches_dates = {'listing', 'start_date', 'end_date'} & serializer.validated_data.keys()
        if not touches_dates:
            serializer.save()
            return

        listing = serializer.validated_data.get('listing', instance.listing)
        start_date = serializer.validated_data.get('start_date', instance.start_date)
        end_date = serializer.validated_data.get('end_date', instance.end_date)

        with transaction.atomic():
            self._lock_and_check_dates(listing, start_date, end_date, exclude_booking_id=instance.pk)
            serializer.save()

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        booking = self.get_object()
        if booking.listing.owner_id != request.user.id:
            return Response({'detail': 'Only the listing owner can confirm this booking'}, status=403)
        if booking.status != BookingStatus.PENDING:
            return Response({'detail': 'Only pending bookings can be confirmed'}, status=400)
        booking.status = BookingStatus.CONFIRMED
        booking.save(update_fields=['status'])
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        booking = self.get_object()
        if booking.listing.owner_id != request.user.id:
            return Response({'detail': 'Only the listing owner can reject this booking'}, status=403)
        if booking.status != BookingStatus.PENDING:
            return Response({'detail': 'Only pending bookings can be rejected'}, status=400)
        booking.status = BookingStatus.REJECTED
        booking.save(update_fields=['status'])
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.tenant_id != request.user.id:
            return Response({'detail': 'Only the tenant can cancel this booking'}, status=403)
        if booking.status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
            return Response({'detail': 'This booking cannot be cancelled'}, status=400)
        if booking.start_date - timezone.now().date() < timedelta(days=CANCELLATION_DEADLINE_DAYS):
            return Response(
                {'detail': f'Bookings can only be cancelled at least {CANCELLATION_DEADLINE_DAYS} day(s) before the start date'},
                status=400,
            )
        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=['status'])
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=['post'], url_path='cancel-by-owner')
    def cancel_by_owner(self, request, pk=None):
        booking = self.get_object()
        if booking.listing.owner_id != request.user.id:
            return Response({'detail': 'Only the listing owner can cancel this booking.'}, status=403)
        if booking.status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
            return Response({'detail': 'This booking cannot be cancelled.'}, status=400)
        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=['status'])
        return Response(self.get_serializer(booking).data)