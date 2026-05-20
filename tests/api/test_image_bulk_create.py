from pathlib import PurePosixPath

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import BULK_IMAGE_LIST_VIEW, JSON
from api.utils import jpeg_data_url

from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from hope_dedup_engine.apps.security.models import User


def test_can_bulk_create_images(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    deduplication_set.state = DeduplicationSet.State.EMPTY
    deduplication_set.save(update_fields=["state"])

    data = [{"reference_pk": f"ref_{i}", "filename": jpeg_data_url(f"payload-{i}".encode())} for i in range(10)]
    response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=data,
        format=JSON,
    )
    assert response.status_code == status.HTTP_201_CREATED


def test_bulk_create_sets_uploading_in_progress(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    deduplication_set.state = DeduplicationSet.State.EMPTY
    deduplication_set.save(update_fields=["state"])

    data = [{"reference_pk": "ref_1", "filename": jpeg_data_url()}]
    response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=data,
        format=JSON,
    )
    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == DeduplicationSet.State.UPLOADING_IN_PROGRESS


def test_bulk_create_stays_uploading_in_progress(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    deduplication_set.state = DeduplicationSet.State.UPLOADING_IN_PROGRESS
    deduplication_set.save(update_fields=["state"])

    data = [{"reference_pk": "ref_1", "filename": jpeg_data_url()}]
    response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=data,
        format=JSON,
    )
    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == DeduplicationSet.State.UPLOADING_IN_PROGRESS


def test_cannot_upload_in_non_uploadable_state(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    data = [{"reference_pk": "ref_1", "filename": jpeg_data_url()}]
    response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=data,
        format=JSON,
    )
    assert response.status_code == status.HTTP_409_CONFLICT


def test_deduplication_set_is_updated(api_client: APIClient, user: User, deduplication_set: DeduplicationSet) -> None:
    deduplication_set.state = DeduplicationSet.State.EMPTY
    deduplication_set.save(update_fields=["state"])
    assert deduplication_set.updated_by is None

    data = [{"reference_pk": "ref_1", "filename": jpeg_data_url()}]
    response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=data,
        format=JSON,
    )

    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user


def test_images_with_same_reference_pk_is_updated(
    api_client: APIClient, deduplication_set: DeduplicationSet, encoding_factory
) -> None:
    deduplication_set.state = DeduplicationSet.State.EMPTY
    deduplication_set.save(update_fields=["state"])
    number_of_images = 10
    images = encoding_factory.create_batch(number_of_images, deduplication_set=deduplication_set)

    data = [
        {"reference_pk": img.reference_pk, "filename": jpeg_data_url(f"updated-{i}".encode())}
        for i, img in enumerate(images)
    ]
    response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=data,
        format=JSON,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Encoding.objects.filter(deduplication_set=deduplication_set).count() == number_of_images
    for image in images:
        image.refresh_from_db()
        assert image.filename.name.startswith(f"images/{deduplication_set.group.reference_pk}/{deduplication_set.pk}/")
        assert PurePosixPath(image.filename.name).name.startswith(image.reference_pk)
