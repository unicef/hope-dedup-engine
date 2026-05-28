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


def test_bulk_create_rejects_non_data_url_filename(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    deduplication_set.state = DeduplicationSet.State.EMPTY
    deduplication_set.save(update_fields=["state"])

    response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=[{"reference_pk": "ref_1", "filename": "plain-text.jpg"}],
        format=JSON,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "filename must be a base64 data URL" in str(response.data)


def test_bulk_create_rejects_invalid_base64_payload(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    deduplication_set.state = DeduplicationSet.State.EMPTY
    deduplication_set.save(update_fields=["state"])

    response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=[{"reference_pk": "ref_1", "filename": "data:image/jpeg;base64,!!!not-valid!!!"}],
        format=JSON,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "filename payload is not valid base64" in str(response.data)


def test_reupload_replaces_existing_storage_file(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    deduplication_set.state = DeduplicationSet.State.EMPTY
    deduplication_set.save(update_fields=["state"])
    reference_pk = "ref-reupload"
    first_payload = b"first-image-bytes"
    second_payload = b"second-image-bytes-replacement"

    first_response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=[{"reference_pk": reference_pk, "filename": jpeg_data_url(first_payload)}],
        format=JSON,
    )
    assert first_response.status_code == status.HTTP_201_CREATED

    encoding = Encoding.objects.get(deduplication_set=deduplication_set, reference_pk=reference_pk)
    storage_path = encoding.filename.name
    storage = encoding.filename.storage
    with storage.open(storage_path, "rb") as fh:
        assert fh.read() == first_payload

    second_response = api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}),
        data=[{"reference_pk": reference_pk, "filename": jpeg_data_url(second_payload)}],
        format=JSON,
    )
    assert second_response.status_code == status.HTTP_201_CREATED

    encoding.refresh_from_db()
    assert encoding.filename.name == storage_path
    with storage.open(storage_path, "rb") as fh:
        assert fh.read() == second_payload
