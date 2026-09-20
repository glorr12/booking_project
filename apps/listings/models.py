from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from djmoney.models.fields import MoneyField
from simple_history.models import HistoricalRecords

from core.models import SoftDeleteModel, TimeStampedModel, UniqueID


class HousingType(models.TextChoices):
    """
    Типы жилья, доступные для размещения в системе бронирования
    """
    APARTMENT = 'apartment', 'Apartment'
    HOUSE = 'house', 'House'
    STUDIO = 'studio', 'Studio'


class Listing(UniqueID, TimeStampedModel, SoftDeleteModel):
    """
    Основная модель объекта недвижимости (листинга)
    в моделе реализованы:
    Защищена от удаления владельца.
    Поддерживает мягкое удаление.
    Содержит ограничения на уровне СУБД для проверки минимального количества комнат и гостей
    Индексирована для ускорения фильтрации по активности, дате создания, городу, типу жилья и валюте цены.
    """
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
    max_guests = models.PositiveIntegerField(default=1, verbose_name='Max guests')

    history = HistoricalRecords()

    def __str__(self):
        return self.title

    class Meta:
        db_table = 'listings'
        ordering = ('-created_at',)
        verbose_name = 'Listing'
        verbose_name_plural = 'Listings'
        constraints = [
            models.CheckConstraint(
                condition=Q(rooms_count__gte=1),
                name='listing_rooms_count_at_least_1',
            ),
            models.CheckConstraint(
                condition=Q(max_guests__gte=1),
                name='listing_max_guests_at_least_1',
            ),
        ]
    indexes = [
        models.Index(fields=['is_active', '-created_at'], name='listing_active_created_index'),
        models.Index(fields=['city'],name="listing_city_index"),
        models.Index(fields=['housing_type'],name="listing_housing_type_index"),
        models.Index(fields=['price_currency'],name="listing_price_index"),
    ]

class ListingImage(UniqueID, TimeStampedModel):
    """
    Модель изображений, привязанных к объекту недвижимости
    """
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Listing',
    )
    image = models.ImageField(upload_to='listings/photos', verbose_name='Image')
    order = models.PositiveIntegerField(default=0, verbose_name='Order')

    def __str__(self):
        return f'Image for {self.listing_id} (#{self.order})'

    class Meta:
        db_table = 'listing_images'
        ordering = ('order', 'created_at')
        verbose_name = 'Listing image'
        verbose_name_plural = 'Listing images'


class BlockedDateRange(UniqueID, TimeStampedModel):
    """
    Модель заблокированных владельцем дат для листинга (периоды, когда объект недоступен для бронирования)
    """
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='blocked_dates',
        verbose_name='Listing',
    )
    start_date = models.DateField(verbose_name='Start date')
    end_date = models.DateField(verbose_name='End date')
    reason = models.CharField(max_length=255, blank=True, verbose_name='Reason')

    def clean(self):
        """
        Проверяет корректность диапазона дат перед сохранением
        """
        super().clean()
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError('End date must be after start date.')

    def __str__(self):
        return f'{self.listing_id} blocked {self.start_date} -> {self.end_date}'

    class Meta:
        db_table = 'listing_blocked_dates'
        ordering = ('-start_date',)
        verbose_name = 'Blocked date range'
        verbose_name_plural = 'Blocked date ranges'
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gt=F('start_date')),
                name='blocked_range_end_date_after_start_date',
            ),
        ]
        indexes = [
            models.Index(fields=['listing', 'start_date', 'end_date'], name='blocked_range_overlap_index'),
        ]