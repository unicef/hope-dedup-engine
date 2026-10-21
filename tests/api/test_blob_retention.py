"""Images live in the shared HOPE blob storage, so deleting rows must never delete blobs."""

from collections.abc import Callable, Iterator

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import Storage, storages
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import BULK_IMAGE_CLEAR_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding

pytestmark = pytest.mark.django_db


@pytest.fixture
def hope_storage() -> Storage:
    return storages["hope"]


@pytest.fixture
def blob_encoding(deduplication_set: DeduplicationSet, hope_storage: Storage) -> Iterator[Encoding]:
    key = hope_storage.save("hope/test-blob-retention/image.jpg", ContentFile(b"image-bytes"))
    encoding = Encoding.objects.create(deduplication_set=deduplication_set, reference_pk="ref-blob", filename=key)
    yield encoding
    hope_storage.delete(key)


def test_deleting_an_encoding_keeps_its_blob(
    blob_encoding: Encoding,
    hope_storage: Storage,
    django_capture_on_commit_callbacks: Callable,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        blob_encoding.delete()

    assert not Encoding.objects.filter(pk=blob_encoding.pk).exists()
    assert hope_storage.exists(blob_encoding.filename)


def test_bulk_deleting_encodings_keeps_blobs(
    blob_encoding: Encoding,
    hope_storage: Storage,
    django_capture_on_commit_callbacks: Callable,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        Encoding.objects.filter(pk=blob_encoding.pk).delete()

    assert not Encoding.objects.filter(pk=blob_encoding.pk).exists()
    assert hope_storage.exists(blob_encoding.filename)


def test_deleting_a_deduplication_set_keeps_blobs(
    blob_encoding: Encoding,
    hope_storage: Storage,
    django_capture_on_commit_callbacks: Callable,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        blob_encoding.deduplication_set.delete()

    assert not Encoding.objects.filter(pk=blob_encoding.pk).exists()
    assert hope_storage.exists(blob_encoding.filename)


def test_clear_images_endpoint_keeps_blobs(
    api_client: APIClient,
    blob_encoding: Encoding,
    hope_storage: Storage,
    django_capture_on_commit_callbacks: Callable,
) -> None:
    url = reverse(BULK_IMAGE_CLEAR_VIEW, kwargs={"deduplication_set_pk": blob_encoding.deduplication_set_id})

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.delete(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Encoding.objects.filter(pk=blob_encoding.pk).exists()
    assert hope_storage.exists(blob_encoding.filename)
