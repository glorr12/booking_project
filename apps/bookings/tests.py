from datetime import date, timedelta

import pytest
from django.core.management import call_command
from djmoney.money import Money

from apps.bookings.models import Booking, BookingStatus


@pytest.fixture
def pending_booking(db, listing, tenant):
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=5)
    return Booking.objects.create(listing=listing, tenant=tenant, start_date=start, end_date=end)


@pytest.mark.django_db
def test_tenant_can_create_booking(auth_client, tenant, listing):
    client = auth_client(tenant)
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=5)

    response = client.post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(end),
    }, format='json')

    assert response.status_code == 201
    assert response.data['status'] == BookingStatus.PENDING


@pytest.mark.django_db
def test_end_date_before_start_date_rejected(auth_client, tenant, listing):
    client = auth_client(tenant)
    start = date.today() + timedelta(days=10)

    response = client.post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(start - timedelta(days=1)),
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_start_date_in_past_rejected(auth_client, tenant, listing):
    client = auth_client(tenant)
    start = date.today() - timedelta(days=5)

    response = client.post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(start + timedelta(days=2)),
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_booking_longer_than_max_duration_rejected(auth_client, tenant, listing):
    client = auth_client(tenant)
    start = date.today() + timedelta(days=10)

    response = client.post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(start + timedelta(days=31)),
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_booking_at_exactly_max_duration_allowed(auth_client, tenant, listing):
    client = auth_client(tenant)
    start = date.today() + timedelta(days=10)

    response = client.post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(start + timedelta(days=30)),
    }, format='json')

    assert response.status_code == 201


@pytest.mark.django_db
def test_overlapping_dates_rejected(auth_client, tenant, other_tenant, listing, pending_booking):
    client = auth_client(other_tenant)

    response = client.post('/api/bookings/', {
        'listing': str(listing.pk),
        'start_date': str(pending_booking.start_date + timedelta(days=1)),
        'end_date': str(pending_booking.end_date + timedelta(days=1)),
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_only_listing_owner_can_confirm(auth_client, tenant, landlord, other_landlord, pending_booking):
    response = auth_client(other_landlord).post(f'/api/bookings/{pending_booking.pk}/confirm/')
    assert response.status_code == 404

    response = auth_client(landlord).post(f'/api/bookings/{pending_booking.pk}/confirm/')
    assert response.status_code == 200
    assert response.data['status'] == BookingStatus.CONFIRMED


@pytest.mark.django_db
def test_confirming_non_pending_booking_rejected(auth_client, landlord, pending_booking):
    pending_booking.status = BookingStatus.CANCELLED
    pending_booking.save(update_fields=['status'])

    response = auth_client(landlord).post(f'/api/bookings/{pending_booking.pk}/confirm/')

    assert response.status_code == 400


@pytest.mark.django_db
def test_only_tenant_can_cancel(auth_client, landlord, tenant, other_tenant, pending_booking):
    response = auth_client(landlord).post(f'/api/bookings/{pending_booking.pk}/cancel/')
    assert response.status_code == 403

    response = auth_client(tenant).post(f'/api/bookings/{pending_booking.pk}/cancel/')
    assert response.status_code == 200
    assert response.data['status'] == BookingStatus.CANCELLED


@pytest.mark.django_db
def test_cancellation_deadline_enforced(auth_client, tenant, listing):
    client = auth_client(tenant)
    start = date.today()
    end = start + timedelta(days=2)
    booking = Booking.objects.create(listing=listing, tenant=tenant, start_date=start, end_date=end)

    response = client.post(f'/api/bookings/{booking.pk}/cancel/')

    assert response.status_code == 400
    booking.refresh_from_db()
    assert booking.status == BookingStatus.PENDING


@pytest.mark.django_db
def test_booking_snapshots_price_at_creation(auth_client, tenant, listing):
    client = auth_client(tenant)
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=4)  # 4 nights

    response = client.post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(end),
    }, format='json')
    assert response.status_code == 201

    booking = Booking.objects.get(pk=response.data['id'])
    assert booking.total_price == Money(4000, 'EUR')  # 1000/night * 4 nights

    listing.price = Money(2000, 'EUR')
    listing.save(update_fields=['price', 'price_currency'])
    booking.refresh_from_db()
    assert booking.total_price == Money(4000, 'EUR')


@pytest.mark.django_db
def test_owner_can_cancel_confirmed_booking(auth_client, landlord, pending_booking):
    pending_booking.status = BookingStatus.CONFIRMED
    pending_booking.save(update_fields=['status'])

    response = auth_client(landlord).post(f'/api/bookings/{pending_booking.pk}/cancel-by-owner/')

    assert response.status_code == 200
    assert response.data['status'] == BookingStatus.CANCELLED


@pytest.mark.django_db
def test_owner_cancel_ignores_notice_period(auth_client, landlord, tenant, listing):
    start = date.today()
    booking = Booking.objects.create(listing=listing, tenant=tenant, start_date=start, end_date=start + timedelta(days=2))

    response = auth_client(landlord).post(f'/api/bookings/{booking.pk}/cancel-by-owner/')

    assert response.status_code == 200
    assert response.data['status'] == BookingStatus.CANCELLED


@pytest.mark.django_db
def test_tenant_cannot_cancel_by_owner(auth_client, tenant, pending_booking):
    response = auth_client(tenant).post(f'/api/bookings/{pending_booking.pk}/cancel-by-owner/')

    assert response.status_code == 403


@pytest.mark.django_db
def test_complete_past_bookings_command_marks_only_past_confirmed(listing, tenant):
    today = date.today()
    past_confirmed = Booking.objects.create(
        listing=listing, tenant=tenant,
        start_date=today - timedelta(days=10), end_date=today - timedelta(days=5),
        status=BookingStatus.CONFIRMED,
    )
    future_confirmed = Booking.objects.create(
        listing=listing, tenant=tenant,
        start_date=today + timedelta(days=5), end_date=today + timedelta(days=8),
        status=BookingStatus.CONFIRMED,
    )
    past_pending = Booking.objects.create(
        listing=listing, tenant=tenant,
        start_date=today - timedelta(days=10), end_date=today - timedelta(days=5),
        status=BookingStatus.PENDING,
    )

    call_command('complete_past_bookings')

    past_confirmed.refresh_from_db()
    future_confirmed.refresh_from_db()
    past_pending.refresh_from_db()
    assert past_confirmed.status == BookingStatus.COMPLETED
    assert future_confirmed.status == BookingStatus.CONFIRMED
    assert past_pending.status == BookingStatus.PENDING
    assert past_confirmed.history.filter(status=BookingStatus.COMPLETED).exists()


@pytest.mark.django_db
def test_perform_create_rechecks_overlap_missed_by_validate(monkeypatch, auth_client, tenant, other_tenant, listing):
    from apps.bookings.serializers import BookingSerializer

    start = date.today() + timedelta(days=15)
    end = start + timedelta(days=3)

    monkeypatch.setattr(BookingSerializer, 'validate', lambda self, attrs: attrs)

    Booking.objects.create(listing=listing, tenant=other_tenant, start_date=start, end_date=end)

    response = auth_client(tenant).post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(end),
    }, format='json')

    assert response.status_code == 400
    assert Booking.objects.filter(listing=listing, start_date=start, end_date=end).count() == 1

@pytest.mark.django_db
def test_total_price_recalculated_on_date_change(auth_client, tenant, listing):
    client = auth_client(tenant)
    start = date.today() + timedelta(days=10)

    response = client.post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(start + timedelta(days=2)),
    }, format='json')
    assert response.data['total_price'] == '2000.00'
    booking_id = response.data['id']

    response = client.patch(f'/api/bookings/{booking_id}/', {
        'end_date': str(start + timedelta(days=10)),
    }, format='json')

    assert response.status_code == 200
    assert response.data['total_price'] == '10000.00'
    booking = Booking.objects.get(pk=booking_id)
    assert booking.total_price == Money(10000, 'EUR')


@pytest.mark.django_db
def test_cannot_change_dates_once_confirmed(auth_client, landlord, tenant, pending_booking):
    auth_client(landlord).post(f'/api/bookings/{pending_booking.pk}/confirm/')

    response = auth_client(tenant).patch(f'/api/bookings/{pending_booking.pk}/', {
        'end_date': str(pending_booking.end_date + timedelta(days=5)),
    }, format='json')

    assert response.status_code == 400
    pending_booking.refresh_from_db()
    assert pending_booking.end_date != pending_booking.end_date + timedelta(days=5)


@pytest.mark.django_db
def test_guests_count_over_listing_max_rejected(auth_client, tenant, listing):
    listing.max_guests = 2
    listing.save(update_fields=['max_guests'])
    start = date.today() + timedelta(days=10)

    response = auth_client(tenant).post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(start + timedelta(days=2)),
        'guests_count': 5,
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_guests_count_defaults_to_one(auth_client, tenant, listing):
    start = date.today() + timedelta(days=10)

    response = auth_client(tenant).post('/api/bookings/', {
        'listing': str(listing.pk), 'start_date': str(start), 'end_date': str(start + timedelta(days=2)),
    }, format='json')

    assert response.status_code == 201
    assert response.data['guests_count'] == 1


@pytest.mark.django_db
def test_booking_rejected_on_owner_blocked_dates(auth_client, tenant, listing):
    from apps.listings.models import BlockedDateRange

    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=5)
    BlockedDateRange.objects.create(listing=listing, start_date=start, end_date=end, reason='Renovation')

    response = auth_client(tenant).post('/api/bookings/', {
        'listing': str(listing.pk),
        'start_date': str(start + timedelta(days=1)), 'end_date': str(start + timedelta(days=3)),
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_expire_pending_bookings_command(listing, tenant):
    from apps.bookings.management.commands.expire_pending_bookings import CONFIRMATION_DEADLINE_HOURS

    overdue = Booking.objects.create(
        listing=listing, tenant=tenant,
        start_date=date.today() + timedelta(days=20), end_date=date.today() + timedelta(days=22),
    )
    Booking.objects.filter(pk=overdue.pk).update(
        created_at=timezone_now_minus_hours(CONFIRMATION_DEADLINE_HOURS + 1)
    )

    recent = Booking.objects.create(
        listing=listing, tenant=tenant,
        start_date=date.today() + timedelta(days=25), end_date=date.today() + timedelta(days=27),
    )

    call_command('expire_pending_bookings')

    overdue.refresh_from_db()
    recent.refresh_from_db()
    assert overdue.status == BookingStatus.EXPIRED
    assert recent.status == BookingStatus.PENDING
    assert overdue.history.filter(status=BookingStatus.EXPIRED).exists()


def timezone_now_minus_hours(hours):
    from django.utils import timezone
    return timezone.now() - timedelta(hours=hours)