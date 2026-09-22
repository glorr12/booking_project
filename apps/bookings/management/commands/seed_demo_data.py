"""Seeds the database with fake but realistic data - landlords, tenants, listings, photos,
bookings, reviews, and search/view logs - so there is something to click through during a
demo/defense.

EN: Everything created here uses an `@demo.local` email so it can be found and wiped again with
`--flush` without touching real accounts. All seeded users share one password (see
DEMO_PASSWORD below) so you can log in as any of them during a demo.
RU: Все созданные здесь пользователи имеют email на `@demo.local`, чтобы их можно было найти и
удалить через `--flush`, не затрагивая настоящие аккаунты. У всех один и тот же пароль (см.
DEMO_PASSWORD ниже) - можно зайти под любым из них при демонстрации.

Usage:
    python manage.py seed_demo_data                  # add demo data on top of what's there
    python manage.py seed_demo_data --flush           # wipe old demo data first, then re-seed
    python manage.py seed_demo_data --flush-only       # only wipe, don't create anything new
"""

import io
import random
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from djmoney.money import Money
from faker import Faker
from PIL import Image, ImageDraw

from apps.bookings.models import Booking, BookingStatus
from apps.listings.models import BlockedDateRange, HousingType, Listing, ListingImage
from apps.reviews.models import Review
from apps.statistics.models import ListingView, SearchQuery
from apps.users.models import AccountRole, User

DEMO_EMAIL_SUFFIX = '@demo.local'
DEMO_PASSWORD = 'DemoPass123'

CITIES = ['Berlin', 'Munich', 'Hamburg', 'Cologne', 'Frankfurt', 'Lisbon', 'Porto', 'Lyon', 'Prague']
LISTING_ADJECTIVES = [
    'Cozy', 'Bright', 'Modern', 'Spacious', 'Charming', 'Sunny', 'Quiet', 'Stylish',
    'Renovated', 'Central',
]
SEARCH_KEYWORDS = [
    'studio berlin', 'apartment with balcony', 'cheap house', 'sea view', 'pet friendly',
    'near metro', 'house with garden', 'munich center', 'quiet street', 'family apartment',
]
# EN: Solid-colour placeholders, not photos of real properties - there's no legitimate stock of
# "photos of this listing" to draw from for a fake listing, and pulling random photos off the
# web would risk using someone's real photo without any right to. Generated locally instead.
# RU: Однотонные заглушки, а не фотографии реальных объектов - для несуществующего объявления
# просто неоткуда взять "его настоящие фото", а тянуть случайные фото из интернета означало бы
# использовать чьи-то реальные снимки без всякого права на это. Поэтому генерируются на месте.
PHOTO_COLORS = [
    (196, 164, 132), (139, 172, 182), (168, 196, 158), (214, 178, 158),
    (176, 158, 196), (196, 196, 158), (158, 176, 196), (196, 158, 168),
]


class Command(BaseCommand):
    help = 'Seeds the database with demo data (landlords, tenants, listings, bookings, reviews) for a presentation/defense.'

    def add_arguments(self, parser):
        parser.add_argument('--landlords', type=int, default=5, help='Number of landlord accounts to create.')
        parser.add_argument('--tenants', type=int, default=10, help='Number of tenant accounts to create.')
        parser.add_argument('--listings-per-landlord', type=int, default=3)
        parser.add_argument('--bookings', type=int, default=40, help='Total bookings to create across all listings.')
        parser.add_argument('--locale', type=str, default='en_US', help="Faker locale, e.g. 'ru_RU' for Cyrillic names/text.")
        parser.add_argument('--flush', action='store_true', help='Delete previously seeded demo data before creating new data.')
        parser.add_argument('--flush-only', action='store_true', help='Only delete previously seeded demo data, then exit.')

    def handle(self, *args, **options):
        if options['flush'] or options['flush_only']:
            self._flush()
            if options['flush_only']:
                return

        fake = Faker(options['locale'])

        with transaction.atomic():
            landlords = self._create_users(fake, options['landlords'], AccountRole.LANDLORD, 'landlord')
            tenants = self._create_users(fake, options['tenants'], AccountRole.TENANT, 'tenant')
            listings = self._create_listings(fake, landlords, options['listings_per_landlord'])
            self._create_blocked_ranges(fake, listings)
            images_count = self._create_listing_images(listings)
            bookings = self._create_bookings(fake, tenants, listings, options['bookings'])
            reviews_count = self._create_reviews(fake, bookings)
            self._create_statistics(tenants, listings)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(landlords)} landlords, {len(tenants)} tenants, {len(listings)} listings, '
            f'{images_count} photos, {len(bookings)} bookings, {reviews_count} reviews.'
        ))
        self.stdout.write(self.style.SUCCESS(f'All demo accounts share the password: {DEMO_PASSWORD}'))
        self.stdout.write('Example login: ' + (landlords[0].email if landlords else '(none created)'))

    # -- cleanup -----------------------------------------------------------------------------

    def _flush(self):
        """EN: Listings first (PROTECT on Listing.owner would otherwise block deleting
        landlords) - deleting them cascades away their bookings/reviews/images/blocked
        ranges/view logs automatically. Then the demo users themselves.
        RU: Сначала объявления (иначе PROTECT на Listing.owner не даст удалить арендодателей) -
        их удаление каскадно уносит брони/отзывы/фото/блокировки/просмотры. Потом самих
        демо-пользователей."""
        # EN: QuerySet.delete() only removes the DB rows - it does NOT touch the actual files
        # in media/, so the generated JPEGs from a previous run would otherwise pile up on disk
        # forever across repeated --flush/reseed cycles. Collect and remove those files first.
        # RU: QuerySet.delete() удаляет только строки в БД - сами файлы в media/ он не трогает,
        # поэтому сгенерированные JPEG'и с прошлого запуска иначе копились бы на диске бесконечно
        # при повторных циклах --flush/пересоздания. Сначала собираем и удаляем сами файлы.
        image_fields = ListingImage.objects.filter(
            listing__owner__email__endswith=DEMO_EMAIL_SUFFIX
        ).values_list('image', flat=True)
        for name in image_fields:
            if name:
                default_storage.delete(name)

        listings_deleted, _ = Listing.all_objects.filter(owner__email__endswith=DEMO_EMAIL_SUFFIX).delete()
        users_deleted, _ = User.all_objects.filter(email__endswith=DEMO_EMAIL_SUFFIX).delete()
        self.stdout.write(f'Flushed previous demo data: {listings_deleted} listing-related row(s), {users_deleted} user(s).')

    # -- users ---------------------------------------------------------------------------------

    def _create_users(self, fake, count, role, label):
        users = []
        for i in range(1, count + 1):
            email = f'{label}{i}{DEMO_EMAIL_SUFFIX}'
            user = User.objects.create_user(
                email=email,
                password=DEMO_PASSWORD,
                name=fake.name(),
                role=role,
            )
            users.append(user)
        return users

    # -- listings --------------------------------------------------------------------------

    def _create_listings(self, fake, landlords, per_landlord):
        housing_types = list(HousingType.values)
        listings = []
        for landlord in landlords:
            for _ in range(per_landlord):
                rooms = random.randint(1, 5)
                listings.append(Listing.objects.create(
                    owner=landlord,
                    # EN: a fixed English adjective list, not fake.word() - with a non-English
                    # --locale, fake.word() would mix e.g. a Russian word into an otherwise
                    # English title ("in Lisbon"), which looks broken on a demo screen.
                    # RU: фиксированный список английских прилагательных, а не fake.word() - при
                    # нерусской/неанглийской --locale fake.word() подмешивал бы, например,
                    # русское слово в англоязычный заголовок ("in Lisbon"), что на экране во
                    # время защиты выглядело бы как баг.
                    title=f'{random.choice(LISTING_ADJECTIVES)} {random.choice(["studio", "flat", "house", "loft"])} in {random.choice(CITIES)}',
                    description=fake.paragraph(nb_sentences=4),
                    city=random.choice(CITIES),
                    district=fake.street_name(),
                    price=Money(Decimal(random.randrange(300, 3000, 50)), 'EUR'),
                    rooms_count=rooms,
                    housing_type=random.choice(housing_types),
                    max_guests=random.randint(1, rooms * 2),
                ))
        return listings

    def _create_blocked_ranges(self, fake, listings):
        today = timezone.now().date()
        for listing in listings:
            if random.random() < 0.4:  # not every listing has an owner-blocked range
                start = today + timedelta(days=random.randint(60, 120))
                BlockedDateRange.objects.create(
                    listing=listing,
                    start_date=start,
                    end_date=start + timedelta(days=random.randint(2, 7)),
                    reason=random.choice(['Maintenance', 'Owner staying', 'Renovation']),
                )

    # -- photos --------------------------------------------------------------------------------

    def _create_listing_images(self, listings):
        created = 0
        for listing in listings:
            for order in range(random.randint(1, 4)):
                content = self._generate_placeholder_photo(listing.title, order)
                ListingImage.objects.create(
                    listing=listing,
                    image=ContentFile(content, name=f'{listing.id}_{order}.jpg'),
                    order=order,
                )
                created += 1
        return created

    @staticmethod
    def _generate_placeholder_photo(label, seed):
        """EN: A simple in-memory JPEG - a solid colour with the listing's title drawn on it -
        so `image` is a real, valid image file (Pillow/ImageField will happily reject anything
        that isn't) without needing any external images. Cheap and instant even for hundreds of
        listings.
        RU: Простой JPEG в памяти - однотонный фон с заголовком объявления - чтобы `image` был
        настоящим, валидным файлом изображения (Pillow/ImageField не пропустит что попало), без
        необходимости брать внешние картинки. Дёшево и мгновенно даже для сотен объявлений."""
        color = PHOTO_COLORS[seed % len(PHOTO_COLORS)]
        image = Image.new('RGB', (640, 480), color=color)
        draw = ImageDraw.Draw(image)
        draw.text((20, 220), label, fill=(40, 40, 40))
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=85)
        return buffer.getvalue()

    # -- bookings + reviews ------------------------------------------------------------------

    def _create_bookings(self, fake, tenants, listings, total):
        today = timezone.now().date()
        # EN: statuses weighted so COMPLETED dominates - that's what makes reviews possible and
        # what a demo mostly wants to show off.
        # RU: статусы взвешены так, чтобы COMPLETED преобладал - именно он даёт возможность
        # оставить отзыв и именно его в первую очередь хочется показать на защите.
        statuses = (
            [BookingStatus.COMPLETED] * 5
            + [BookingStatus.CONFIRMED] * 2
            + [BookingStatus.PENDING] * 2
            + [BookingStatus.CANCELLED]
            + [BookingStatus.REJECTED]
            + [BookingStatus.EXPIRED]
        )
        booked_ranges = {listing.id: [] for listing in listings}
        bookings = []

        for _ in range(total):
            listing = random.choice(listings)
            tenant = random.choice(tenants)
            status = random.choice(statuses)
            nights = random.randint(2, 10)

            if status in (BookingStatus.COMPLETED, BookingStatus.CANCELLED, BookingStatus.REJECTED, BookingStatus.EXPIRED):
                start = today - timedelta(days=random.randint(nights + 1, 300))
            else:
                start = today + timedelta(days=random.randint(1, 90))
            end = start + timedelta(days=nights)

            if self._overlaps(booked_ranges[listing.id], start, end):
                continue  # skip this draw rather than fight the overlap - there are plenty more
            booked_ranges[listing.id].append((start, end))

            guests = random.randint(1, max(listing.max_guests, 1))
            booking = Booking.objects.create(
                listing=listing,
                tenant=tenant,
                start_date=start,
                end_date=end,
                guests_count=guests,
                status=status,
                total_price=listing.price * nights,
            )
            bookings.append(booking)
        return bookings

    @staticmethod
    def _overlaps(existing_ranges, start, end):
        return any(start < e and end > s for s, e in existing_ranges)

    def _create_reviews(self, fake, bookings):
        reviewed_pairs = set()  # (listing_id, tenant_id) - matches the unique_review_per_listing_and_author constraint
        created = 0
        for booking in bookings:
            if booking.status != BookingStatus.COMPLETED:
                continue
            key = (booking.listing_id, booking.tenant_id)
            if key in reviewed_pairs or random.random() < 0.25:  # not every completed stay gets reviewed
                continue
            reviewed_pairs.add(key)
            Review.objects.create(
                booking=booking,
                listing=booking.listing,
                author=booking.tenant,
                rating=random.randint(1, 5),
                text=fake.paragraph(nb_sentences=2),
            )
            created += 1
        return created

    # -- statistics logs ---------------------------------------------------------------------

    def _create_statistics(self, tenants, listings):
        for _ in range(80):
            SearchQuery.objects.create(
                keyword=random.choice(SEARCH_KEYWORDS),
                user=random.choice(tenants) if random.random() < 0.7 else None,
            )
        for listing in listings:
            for _ in range(random.randint(0, 25)):
                ListingView.objects.create(
                    listing=listing,
                    user=random.choice(tenants) if random.random() < 0.8 else None,
                )
