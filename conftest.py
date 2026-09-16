import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.listings.models import HousingType, Listing
from apps.users.models import AccountRole, User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client():
    def _make(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client
    return _make


@pytest.fixture
def landlord(db):
    return User.objects.create_user(
        email='landlord@test.com', password='pass12345', name='Landlord', role=AccountRole.LANDLORD,
    )


@pytest.fixture
def other_landlord(db):
    return User.objects.create_user(
        email='other-landlord@test.com', password='pass12345', name='Other Landlord', role=AccountRole.LANDLORD,
    )


@pytest.fixture
def tenant(db):
    return User.objects.create_user(
        email='tenant@test.com', password='pass12345', name='Tenant', role=AccountRole.TENANT,
    )


@pytest.fixture
def other_tenant(db):
    return User.objects.create_user(
        email='other-tenant@test.com', password='pass12345', name='Other Tenant', role=AccountRole.TENANT,
    )


@pytest.fixture
def listing(db, landlord):
    return Listing.objects.create(
        owner=landlord,
        title='Cozy flat in Berlin',
        description='A nice place to stay',
        city='Berlin',
        district='Mitte',
        rooms_count=2,
        housing_type=HousingType.APARTMENT,
        price=1000,
    )


@pytest.fixture
def make_image():
    def _make(name='photo.png', color='red'):
        buf = io.BytesIO()
        Image.new('RGB', (10, 10), color=color).save(buf, format='PNG')
        buf.seek(0)
        return SimpleUploadedFile(name, buf.read(), content_type='image/png')
    return _make