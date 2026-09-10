from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from simple_history.models import HistoricalRecords

from core.models import TimeStampedModel, UniqueID


class BookingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    REJECTED = 'rejected', 'Rejected'
    CANCELLED = 'cancelled', 'Cancelled'
    COMPLETED = 'completed', 'Completed'


class Booking(UniqueID, TimeStampedModel):
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name='Listing',
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name='Tenant',
    )
    start_date = models.DateField(verbose_name='Start date')
    end_date = models.DateField(verbose_name='End date')
    status = models.CharField(
        max_length=10,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        verbose_name='Status',
    )

    history = HistoricalRecords()

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError('End date must be after start date.')

    def __str__(self):
        return f'Booking #{self.pk}: {self.start_date} -> {self.end_date}'

    class Meta:
        db_table = 'bookings'
        ordering = ('-start_date',)
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gt=F('start_date')),
                name='booking_end_date_after_start_date',
            ),
        ]