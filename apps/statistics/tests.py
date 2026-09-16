import pytest

from apps.statistics.models import ListingView, SearchQuery


@pytest.mark.django_db
def test_popular_listings_orders_by_view_count(api_client, listing):
    ListingView.objects.create(listing=listing)
    ListingView.objects.create(listing=listing)

    response = api_client.get('/api/statistics/popular-listings/')

    assert response.status_code == 200
    assert response.data[0]['id'] == str(listing.pk)
    assert response.data[0]['views_count'] == 2


@pytest.mark.django_db
def test_popular_searches_counts_keywords(api_client):
    SearchQuery.objects.create(keyword='Berlin')
    SearchQuery.objects.create(keyword='Berlin')
    SearchQuery.objects.create(keyword='Munich')

    response = api_client.get('/api/statistics/popular-searches/')

    assert response.status_code == 200
    top = {row['keyword']: row['count'] for row in response.data}
    assert top['Berlin'] == 2
    assert top['Munich'] == 1

@pytest.mark.django_db
def test_popular_listings_views_and_ratings_stay_correct_together(api_client, listing, tenant, other_tenant):
    from datetime import date, timedelta

    from apps.bookings.models import Booking, BookingStatus
    from apps.reviews.models import Review

    ListingView.objects.create(listing=listing)
    ListingView.objects.create(listing=listing)
    ListingView.objects.create(listing=listing)

    for user, rating in ((tenant, 4), (other_tenant, 2)):
        booking = Booking.objects.create(
            listing=listing, tenant=user,
            start_date=date.today() - timedelta(days=10), end_date=date.today() - timedelta(days=5),
            status=BookingStatus.COMPLETED,
        )
        Review.objects.create(booking=booking, listing=listing, author=user, rating=rating, text='ok')

    response = api_client.get('/api/statistics/popular-listings/')

    assert response.status_code == 200
    item = response.data[0]
    assert item['views_count'] == 3
    assert item['reviews_count'] == 2
    assert item['average_rating'] == 3.0