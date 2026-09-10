from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel, UniqueID


class Review(UniqueID, TimeStampedModel):
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='review',
        verbose_name='Booking',
    )
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Listing',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Author',
    )
    rating = models.PositiveSmallIntegerField(verbose_name='Rating')
    text = models.TextField(verbose_name='Text')

    def __str__(self):
        return f'Review for listing #{self.listing_id} ({self.rating}/5)'

    class Meta:
        db_table = 'reviews'
        ordering = ('-created_at',)
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5),
                name='review_rating_between_1_and_5',
            ),
            models.UniqueConstraint(
                fields=['listing', 'author'],
                name='unique_review_per_listing_and_author',
            ),
        ]