from datetime import date, timedelta

import pytest

from apps.bookings.models import Booking, BookingStatus
from apps.listings.models import HousingType, Listing, ListingImage
from apps.reviews.models import Review
from apps.statistics.models import ListingView, SearchQuery


@pytest.mark.django_db
def test_landlord_can_create_listing(auth_client, landlord):
    client = auth_client(landlord)

    response = client.post('/api/listings/', {
        'title': 'Sunny studio', 'description': 'desc', 'city': 'Munich',
        'rooms_count': 1, 'housing_type': 'studio', 'price': '500',
    }, format='json')

    assert response.status_code == 201
    assert response.data['owner_name'] == landlord.name


@pytest.mark.django_db
def test_tenant_cannot_create_listing(auth_client, tenant):
    client = auth_client(tenant)

    response = client.post('/api/listings/', {
        'title': 'Should fail', 'description': 'desc', 'city': 'Munich',
        'rooms_count': 1, 'housing_type': 'studio', 'price': '500',
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_owner_can_update_own_listing(auth_client, landlord, listing):
    client = auth_client(landlord)

    response = client.patch(f'/api/listings/{listing.pk}/', {'title': 'Updated title'}, format='json')

    assert response.status_code == 200
    assert response.data['title'] == 'Updated title'


@pytest.mark.django_db
def test_non_owner_cannot_update_listing(auth_client, other_landlord, listing):
    client = auth_client(other_landlord)

    response = client.patch(f'/api/listings/{listing.pk}/', {'title': 'Hacked'}, format='json')

    assert response.status_code == 403


@pytest.mark.django_db
def test_filter_by_city(api_client, listing):
    response = api_client.get('/api/listings/', {'city': 'Berlin'})

    data = response.data['results'] if isinstance(response.data, dict) else response.data
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]['id'] == str(listing.pk)


@pytest.mark.django_db
def test_filter_by_price_range_excludes_out_of_range_listing(api_client, listing):
    response = api_client.get('/api/listings/', {'price_min': 2000})

    data = response.data['results'] if isinstance(response.data, dict) else response.data
    assert response.status_code == 200
    assert len(data) == 0


@pytest.mark.django_db
def test_search_logs_search_query(api_client, listing):
    response = api_client.get('/api/listings/', {'search': 'Berlin'})

    assert response.status_code == 200
    assert SearchQuery.objects.filter(keyword='Berlin').exists()


@pytest.mark.django_db
def test_retrieve_logs_listing_view(api_client, listing):
    response = api_client.get(f'/api/listings/{listing.pk}/')

    assert response.status_code == 200
    assert ListingView.objects.filter(listing=listing).exists()


@pytest.mark.django_db
def test_owner_can_upload_image(auth_client, landlord, listing, make_image):
    client = auth_client(landlord)

    response = client.post('/api/listings/images/', {
        'listing': str(listing.pk), 'image': make_image(), 'order': 0,
    }, format='multipart')

    assert response.status_code == 201
    assert ListingImage.objects.filter(listing=listing).count() == 1


@pytest.mark.django_db
def test_non_owner_cannot_upload_image(auth_client, other_landlord, listing, make_image):
    client = auth_client(other_landlord)

    response = client.post('/api/listings/images/', {
        'listing': str(listing.pk), 'image': make_image(), 'order': 0,
    }, format='multipart')

    assert response.status_code == 400
    assert not ListingImage.objects.filter(listing=listing).exists()


@pytest.mark.django_db
def test_anonymous_cannot_upload_image(api_client, listing, make_image):
    response = api_client.post('/api/listings/images/', {
        'listing': str(listing.pk), 'image': make_image(), 'order': 0,
    }, format='multipart')

    assert response.status_code == 401


@pytest.mark.django_db
def test_non_owner_cannot_delete_image(auth_client, other_landlord, listing, make_image):
    image = ListingImage.objects.create(listing=listing, image=make_image(), order=0)

    response = auth_client(other_landlord).delete(f'/api/listings/images/{image.pk}/')

    assert response.status_code == 403
    assert ListingImage.objects.filter(pk=image.pk).exists()


@pytest.mark.django_db
def test_deactivated_listing_hidden_from_strangers(api_client, auth_client, other_tenant, listing):
    listing.is_active = False
    listing.save(update_fields=['is_active'])

    assert api_client.get(f'/api/listings/{listing.pk}/').status_code == 404
    assert auth_client(other_tenant).get(f'/api/listings/{listing.pk}/').status_code == 404


@pytest.mark.django_db
def test_deactivated_listing_still_visible_to_owner(auth_client, landlord, listing):
    listing.is_active = False
    listing.save(update_fields=['is_active'])

    response = auth_client(landlord).get(f'/api/listings/{listing.pk}/')

    assert response.status_code == 200


@pytest.mark.django_db
def test_deactivated_listing_still_visible_to_tenant_with_booking(auth_client, tenant, listing):
    Booking.objects.create(
        listing=listing, tenant=tenant,
        start_date=date.today() - timedelta(days=10), end_date=date.today() - timedelta(days=5),
        status=BookingStatus.COMPLETED,
    )
    listing.is_active = False
    listing.save(update_fields=['is_active'])

    response = auth_client(tenant).get(f'/api/listings/{listing.pk}/')

    assert response.status_code == 200


@pytest.mark.django_db
def test_deactivated_listing_hidden_from_unrelated_tenant(auth_client, other_tenant, listing):
    listing.is_active = False
    listing.save(update_fields=['is_active'])

    response = auth_client(other_tenant).get(f'/api/listings/{listing.pk}/')

    assert response.status_code == 404


@pytest.mark.django_db
def test_average_rating_and_reviews_count(api_client, listing, tenant, other_tenant):
    for user, rating in ((tenant, 4), (other_tenant, 2)):
        booking = Booking.objects.create(
            listing=listing, tenant=user,
            start_date=date.today() - timedelta(days=10), end_date=date.today() - timedelta(days=5),
            status=BookingStatus.COMPLETED,
        )
        Review.objects.create(booking=booking, listing=listing, author=user, rating=rating, text='ok')

    response = api_client.get(f'/api/listings/{listing.pk}/')

    assert response.status_code == 200
    assert response.data['average_rating'] == 3.0
    assert response.data['reviews_count'] == 2


@pytest.mark.django_db
def test_listing_with_no_reviews_has_null_average(api_client, listing):
    response = api_client.get(f'/api/listings/{listing.pk}/')

    assert response.status_code == 200
    assert response.data['average_rating'] is None
    assert response.data['reviews_count'] == 0


@pytest.mark.django_db
def test_available_by_dates_filter(api_client, listing, tenant):
    Booking.objects.create(
        listing=listing, tenant=tenant,
        start_date=date(2026, 10, 1), end_date=date(2026, 10, 5),
    )

    overlapping = api_client.get('/api/listings/', {'check_in': '2026-10-03', 'check_out': '2026-10-07'})
    non_overlapping = api_client.get('/api/listings/', {'check_in': '2026-10-10', 'check_out': '2026-10-12'})

    overlapping_data = overlapping.data['results'] if isinstance(overlapping.data, dict) else overlapping.data
    non_overlapping_data = non_overlapping.data['results'] if isinstance(non_overlapping.data, dict) else non_overlapping.data
    assert len(overlapping_data) == 0
    assert len(non_overlapping_data) == 1


@pytest.mark.django_db
def test_available_by_dates_filter_ignores_rejected_bookings(api_client, listing, tenant):
    Booking.objects.create(
        listing=listing, tenant=tenant,
        start_date=date(2026, 10, 1), end_date=date(2026, 10, 5), status=BookingStatus.REJECTED,
    )

    response = api_client.get('/api/listings/', {'check_in': '2026-10-02', 'check_out': '2026-10-04'})

    data = response.data['results'] if isinstance(response.data, dict) else response.data
    assert len(data) == 1


@pytest.mark.django_db
def test_listing_list_has_no_n_plus_1_queries(api_client, django_assert_num_queries, landlord):
    for i in range(3):
        listing = Listing.objects.create(
            owner=landlord, title=f'Place {i}', description='desc', city='Berlin',
            rooms_count=1, housing_type=HousingType.APARTMENT, price=500,
        )
        ListingImage.objects.create(listing=listing, image='fake.png', order=0)

    with django_assert_num_queries(3):
        response = api_client.get('/api/listings/')
        assert response.status_code == 200

@pytest.mark.django_db
def test_rooms_count_range_filter(api_client, landlord):
    small = Listing.objects.create(
        owner=landlord, title='Small', description='d', city='Berlin',
        rooms_count=1, housing_type=HousingType.STUDIO, price=300,
    )
    big = Listing.objects.create(
        owner=landlord, title='Big', description='d', city='Berlin',
        rooms_count=4, housing_type=HousingType.HOUSE, price=1500,
    )

    response = api_client.get('/api/listings/', {'rooms_count_min': 2, 'rooms_count_max': 5})

    data = response.data['results'] if isinstance(response.data, dict) else response.data
    ids = {item['id'] for item in data}
    assert str(big.pk) in ids
    assert str(small.pk) not in ids


@pytest.mark.django_db
def test_negative_price_rejected(auth_client, landlord):
    response = auth_client(landlord).post('/api/listings/', {
        'title': 'Bad price', 'description': 'd', 'city': 'Munich',
        'rooms_count': 1, 'housing_type': 'studio', 'price': '-100',
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_zero_rooms_rejected(auth_client, landlord):
    response = auth_client(landlord).post('/api/listings/', {
        'title': 'No rooms', 'description': 'd', 'city': 'Munich',
        'rooms_count': 0, 'housing_type': 'studio', 'price': '100',
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_ordering_by_average_rating(api_client, tenant, other_tenant, landlord):
    low = Listing.objects.create(
        owner=landlord, title='Low rated', description='d', city='Berlin',
        rooms_count=1, housing_type=HousingType.STUDIO, price=300,
    )
    high = Listing.objects.create(
        owner=landlord, title='High rated', description='d', city='Berlin',
        rooms_count=1, housing_type=HousingType.STUDIO, price=300,
    )
    for listing, rating, user in ((low, 1, tenant), (high, 5, other_tenant)):
        booking = Booking.objects.create(
            listing=listing, tenant=user,
            start_date=date.today() - timedelta(days=10), end_date=date.today() - timedelta(days=5),
            status=BookingStatus.COMPLETED,
        )
        Review.objects.create(booking=booking, listing=listing, author=user, rating=rating, text='ok')

    response = api_client.get('/api/listings/', {'ordering': '-average_rating'})

    data = response.data['results'] if isinstance(response.data, dict) else response.data
    ids_in_order = [item['id'] for item in data]
    assert ids_in_order.index(str(high.pk)) < ids_in_order.index(str(low.pk))

@pytest.mark.django_db
def test_owner_can_block_dates(auth_client, landlord, listing):
    response = auth_client(landlord).post('/api/listings/blocked-dates/', {
        'listing': str(listing.pk),
        'start_date': str(date.today() + timedelta(days=10)),
        'end_date': str(date.today() + timedelta(days=15)),
        'reason': 'Renovation',
    }, format='json')

    assert response.status_code == 201


@pytest.mark.django_db
def test_non_owner_cannot_block_dates(auth_client, other_landlord, listing):
    response = auth_client(other_landlord).post('/api/listings/blocked-dates/', {
        'listing': str(listing.pk),
        'start_date': str(date.today() + timedelta(days=10)),
        'end_date': str(date.today() + timedelta(days=15)),
    }, format='json')

    assert response.status_code == 400


@pytest.mark.django_db
def test_availability_filter_excludes_owner_blocked_dates(api_client, listing):
    from apps.listings.models import BlockedDateRange

    BlockedDateRange.objects.create(
        listing=listing, start_date=date(2026, 11, 1), end_date=date(2026, 11, 10), reason='Maintenance',
    )

    overlapping = api_client.get('/api/listings/', {'check_in': '2026-11-05', 'check_out': '2026-11-07'})
    non_overlapping = api_client.get('/api/listings/', {'check_in': '2026-12-01', 'check_out': '2026-12-05'})

    overlapping_data = overlapping.data['results'] if isinstance(overlapping.data, dict) else overlapping.data
    non_overlapping_data = non_overlapping.data['results'] if isinstance(non_overlapping.data, dict) else non_overlapping.data
    assert len(overlapping_data) == 0
    assert len(non_overlapping_data) == 1


@pytest.mark.django_db
def test_max_guests_defaults_to_one(auth_client, landlord):
    response = auth_client(landlord).post('/api/listings/', {
        'title': 'No guests specified', 'description': 'd', 'city': 'Munich',
        'rooms_count': 1, 'housing_type': 'studio', 'price': '500',
    }, format='json')

    assert response.status_code == 201
    assert response.data['max_guests'] == 1