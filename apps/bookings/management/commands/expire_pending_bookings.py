from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import Booking, BookingStatus

CONFIRMATION_DEADLINE_HOURS = 48


class Command(BaseCommand):

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=CONFIRMATION_DEADLINE_HOURS)
        overdue = Booking.objects.filter(status=BookingStatus.PENDING, created_at__lt=cutoff)
        count = 0
        for booking in overdue:
            booking.status = BookingStatus.EXPIRED
            booking.save(update_fields=['status'])
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Expired {count} pending booking(s) past the {CONFIRMATION_DEADLINE_HOURS}h confirmation deadline'
        ))