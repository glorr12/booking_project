import pytest

from apps.users.models import User


@pytest.mark.django_db
def test_register_creates_user_with_hashed_password(api_client):
    response = api_client.post('/api/auth/register/', {
        'email': 'newuser@test.com', 'password': 'StrongPass123', 'name': 'New User', 'role': 'tenant',
    }, format='json')

    assert response.status_code == 201
    user = User.objects.get(email='newuser@test.com')
    assert user.check_password('StrongPass123')
    assert user.password != 'StrongPass123'


@pytest.mark.django_db
def test_register_duplicate_email_rejected(api_client, tenant):
    response = api_client.post('/api/auth/register/', {
        'email': tenant.email, 'password': 'StrongPass123', 'name': 'Someone Else', 'role': 'tenant',
    }, format='json')

    assert response.status_code == 400
    assert 'email' in response.data


@pytest.mark.django_db
def test_login_and_me_flow(api_client, tenant):
    response = api_client.post('/api/auth/token/', {
        'email': tenant.email, 'password': 'pass12345',
    }, format='json')
    assert response.status_code == 200
    access = response.data['access']

    response = api_client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Bearer {access}')
    assert response.status_code == 200
    assert response.data['email'] == tenant.email


@pytest.mark.django_db
def test_login_with_wrong_password_rejected(api_client, tenant):
    response = api_client.post('/api/auth/token/', {
        'email': tenant.email, 'password': 'wrong-password',
    }, format='json')

    assert response.status_code == 401


@pytest.mark.django_db
def test_me_requires_authentication(api_client):
    response = api_client.get('/api/auth/me/')

    assert response.status_code == 401


@pytest.mark.django_db
def test_tenant_can_become_landlord(auth_client, tenant):
    assert tenant.is_landlord is False

    response = auth_client(tenant).post('/api/auth/become-landlord/')

    assert response.status_code == 200
    assert response.data['is_landlord'] is True
    tenant.refresh_from_db()
    assert tenant.is_landlord is True


@pytest.mark.django_db
def test_landlord_created_with_role_kwarg_is_landlord(landlord):
    assert landlord.is_landlord is True


@pytest.mark.django_db
def test_tenant_created_with_role_kwarg_is_not_landlord(tenant):
    assert tenant.is_landlord is False


@pytest.mark.django_db
def test_became_landlord_can_then_create_listing(auth_client, tenant):
    auth_client(tenant).post('/api/auth/become-landlord/')

    response = auth_client(tenant).post('/api/listings/', {
        'title': 'My first listing', 'description': 'desc', 'city': 'Munich',
        'rooms_count': 1, 'housing_type': 'studio', 'price': '500',
    }, format='json')

    assert response.status_code == 201