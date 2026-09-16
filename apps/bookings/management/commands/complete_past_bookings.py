from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import Booking, BookingStatus


class Command(BaseCommand):
    def handle(self, *args, **options):
        today = timezone.now().date()
        past_bookings = Booking.objects.filter(status=BookingStatus.CONFIRMED, end_date__lt=today)
        count = 0
        for booking in past_bookings:
            booking.status = BookingStatus.COMPLETED
            booking.save(update_fields=['status'])
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Marked {count} booking(s) as completed.'))