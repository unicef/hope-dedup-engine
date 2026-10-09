import pytest
from django.urls import reverse
from testutils.factories.biographic import BiographicSetFactory
from testutils.factories.user import SuperUserFactory

pytestmark = pytest.mark.django_db


def test_set_admin_releases_the_program_lock(django_app_factory) -> None:
    app = django_app_factory(csrf_checks=False)
    app.set_user(SuperUserFactory())
    dataset = BiographicSetFactory()
    dataset.group.processing_locked = True
    dataset.group.save(update_fields=["processing_locked"])

    url = reverse("admin:biographic_biographicset_release_processing_lock", args=[dataset.pk])
    assert app.get(url).forms[1].submit().follow().status_code == 200

    dataset.group.refresh_from_db()
    assert dataset.group.processing_locked is False
