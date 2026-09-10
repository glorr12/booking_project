from django.conf import settings
from django.db import models

from core.models import TimeStampedModel, UniqueID


class SearchQuery(UniqueID, TimeStampedModel):

    keyword = models.CharField(max_length=255, verbose_name='Keyword')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_queries',
        verbose_name='User',
    )

    def __str__(self):
        return self.keyword

    class Meta:
        db_table = 'search_queries'
        ordering = ('-created_at',)
        verbose_name = 'Search query'
        verbose_name_plural = 'Search queries'


class ListingView(UniqueID, TimeStampedModel):
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        related_name='view_logs',
        verbose_name='Listing',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='listing_views',
        verbose_name='User',
    )

    def __str__(self):
        return f'View of listing #{self.listing_id}'

    class Meta:
        db_table = 'listing_views'
        ordering = ('-created_at',)
        verbose_name = 'Listing view'
        verbose_name_plural = 'Listing views'