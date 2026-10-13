import pytest
from django.urls import reverse
from testutils.factories.biographic import BiographicGroupFactory, BiographicRecordFactory, BiographicSetFactory
from testutils.factories.user import SuperUserFactory

from hope_dedup_engine.apps.biographic.admin import MARKED_FAILED_ERROR
from hope_dedup_engine.apps.biographic.models import BiographicSet

pytestmark = pytest.mark.django_db

State = BiographicSet.State


@pytest.fixture
def app(django_app_factory, mocked_responses):
    django_app = django_app_factory(csrf_checks=False)
    django_app.set_user(SuperUserFactory(username="superuser"))
    return django_app


def confirm(app, url: str):
    return app.get(url).forms[1].submit().follow()


def button_url(name: str, dataset: BiographicSet) -> str:
    return reverse(f"admin:biographic_biographicset_{name}", args=[dataset.pk])


def test_unlock_processing_releases_the_programs_lock(app):
    dataset = BiographicSetFactory(group=BiographicGroupFactory(processing_locked=True), state=State.DEDUPLICATED)

    confirm(app, button_url("release_processing_lock", dataset))

    dataset.group.refresh_from_db()
    assert dataset.group.processing_locked is False


@pytest.mark.parametrize("state", [State.INDEXING, State.INDEXED, State.DEDUPLICATING])
def test_a_stuck_set_can_be_marked_failed_and_then_retried(app, state):
    dataset = BiographicSetFactory(group=BiographicGroupFactory(processing_locked=True), state=state)

    confirm(app, button_url("mark_failed", dataset))

    dataset.refresh_from_db()
    assert dataset.state == State.FAILED
    assert dataset.error == MARKED_FAILED_ERROR
    assert dataset.group.processing_locked is False
    assert State.INDEXING in BiographicSet.VALID_TRANSITIONS[dataset.state]


def test_record_admin_renders_the_payload(app):
    record = BiographicRecordFactory(payload={"full_name": "Maria Gonzalez"})
    page = app.get(reverse("admin:biographic_biographicrecord_change", args=[record.pk]))
    assert "Maria Gonzalez" in page.text


def test_record_admin_searches_by_name(app):
    BiographicRecordFactory(payload={"full_name": "Maria Gonzalez"}, full_name="Maria Gonzalez")
    BiographicRecordFactory(payload={"full_name": "Ahmad Shah"}, full_name="Ahmad Shah")
    page = app.get(reverse("admin:biographic_biographicrecord_changelist"), {"q": "Gonzalez"})
    assert "Maria Gonzalez" in page.text
    assert "Ahmad Shah" not in page.text
