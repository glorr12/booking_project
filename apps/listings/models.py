from django.conf import settings
from django.db import models
from djmoney.models.fields import MoneyField
from simple_history.models import HistoricalRecords

from core.models import TimeStampedModel, UniqueID


class HousingType(models.TextChoices):
    APARTMENT = 'apartment', 'Apartment'
    HOUSE = 'house', 'House'
    STUDIO = 'studio', 'Studio'


class Listing(UniqueID, TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='listings',
        verbose_name='Owner',
    )
    title = models.CharField(max_length=200, verbose_name='Title')
    description = models.TextField(verbose_name='Description')
    city = models.CharField(max_length=100, verbose_name='City')
    district = models.CharField(max_length=100, blank=True, verbose_name='District')
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='EUR', verbose_name='Price')
    rooms_count = models.PositiveIntegerField(verbose_name='Rooms count')
    housing_type = models.CharField(max_length=20, choices=HousingType.choices, verbose_name='Housing type')
    is_active = models.BooleanField(default=True, verbose_name='Active')

    history = HistoricalRecords()

    def __str__(self):
        return self.title

    class Meta:
        db_table = 'listings'
        ordering = ('-created_at',)
        verbose_name = 'Listing'
        verbose_name_plural = 'Listings'