import pytest


@pytest.mark.django_db
def test_admin_login_page_loads(client):
    """Sanity check that the project boots and Django admin is reachable."""
    response = client.get('/admin/login/')
    assert response.status_code == 200
