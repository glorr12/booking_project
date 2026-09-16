from datetime import date, timedelta

import pytest

from apps.bookings.models import Booking, BookingStatus
from apps.reviews.models import Review


@pytest.fixture
def completed_booking(db, listing, tenant):
    start = date.today() - timedelta(days=10)
    end = start + timedelta(days=5)
    return Booking.objects.create(
        listing=listing, tenant=tenant, start_date=start, end_date=end, status=BookingStatus.COMPLETED,
    )


@pytest.mark.django_db
def test_tenant_can_review_own_completed_booking(auth_client, tenant, completed_booking):
    client = auth_client(tenant)

    response = client.post('/api/reviews/', {
        'booking': str(completed_booking.pk), 'rating': 5, 'text': 'Great stay!',
    }, format='json')

    assert response.status_code == 201
    assert Review.objects.filter(booking=completed_booking).exists()


@pytest.mark.django_db
def test_cannot_review_someone_elses_booking(auth_client, other_tenant, completed_booking):
    client = auth_client(other_tenant)

    response = client.post('/api/reviews/', {
        'booking': str(completed_booking.pk), 'rating': 5, 'text': 'Not mine',
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_cannot_review_non_completed_booking(auth_client, tenant, listing):
    client = auth_client(tenant)
    start = date.today() + timedelta(days=10)
    booking = Booking.objects.create(listing=listing, tenant=tenant, start_date=start, end_date=start + timedelta(days=2))

    response = client.post('/api/reviews/', {
        'booking': str(booking.pk), 'rating': 4, 'text': 'Too early',
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_duplicate_review_rejected(auth_client, tenant, completed_booking):
    client = auth_client(tenant)
    Review.objects.create(booking=completed_booking, listing=completed_booking.listing, author=tenant, rating=5, text='First')

    response = client.post('/api/reviews/', {
        'booking': str(completed_booking.pk), 'rating': 3, 'text': 'Second attempt',
    }, format='json')

    assert response.status_code == 400

@pytest.mark.django_db
def test_rating_above_max_rejected(auth_client, tenant, completed_booking):
    client = auth_client(tenant)

    response = client.post('/api/reviews/', {
        'booking': str(completed_booking.pk), 'rating': 10, 'text': 'Too high',
    }, format='json')

    assert response.status_code == 400
    assert not Review.objects.filter(booking=completed_booking).exists()


@pytest.mark.django_db
def test_rating_below_min_rejected(auth_client, tenant, completed_booking):
    client = auth_client(tenant)

    response = client.post('/api/reviews/', {
        'booking': str(completed_booking.pk), 'rating': 0, 'text': 'Too low',
    }, format='json')

    assert response.status_code == 400
    assert not Review.objects.filter(booking=completed_booking).exists()