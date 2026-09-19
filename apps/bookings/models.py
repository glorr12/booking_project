from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from djmoney.models.fields import MoneyField
from simple_history.models import HistoricalRecords

from core.models import SoftDeleteModel, TimeStampedModel, UniqueID


class BookingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    REJECTED = 'rejected', 'Rejected'
    CANCELLED = 'cancelled', 'Cancelled'
    COMPLETED = 'completed', 'Completed'
    EXPIRED = 'expired', 'Expired'


class Booking(UniqueID, TimeStampedModel, SoftDeleteModel):
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
    guests_count = models.PositiveIntegerField(default=1, verbose_name='Guests count')
    status = models.CharField(
        max_length=10,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        verbose_name='Status',
    )
    total_price = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency='EUR',
        null=True,
        blank=True,
        editable=False,
        verbose_name='Total price',
        help_text="Snapshot of listing.price × nights at the time the booking was made - "
                  "doesn't change if the listing's price changes later.",
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