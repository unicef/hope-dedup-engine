import json
import re
import zipfile
from io import BytesIO
from unittest.mock import MagicMock
from urllib.parse import urlencode
from uuid import uuid4

import numpy as np
import pytest
from django.core.files.base import ContentFile
from pytest_mock import MockerFixture
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import ENCODINGS_EXPORT_CREATE_VIEW, ENCODINGS_EXPORT_STATUS_VIEW
from hope_dedup_engine.apps.api.deduplication.export import (
    EMBEDDINGS_MEMBER,
    ENCODINGS_MEMBER,
    EXPORT_FORMAT_JSONL,
    EXPORT_FORMAT_NPY,
    INDEX_MEMBER,
    MANIFEST_MEMBER,
    build_export_key,
    error_key,
    export_encodings,
    export_key_prefix,
    get_embeddings_storage,
)
from hope_dedup_engine.apps.api.models import DeduplicationSet, HDEToken
from hope_dedup_engine.apps.api.models.deduplication import Encoding

CO_SLUG = "afghanistan"


@pytest.fixture
def encoded_set(
    request: pytest.FixtureRequest,
    deduplication_set: DeduplicationSet,
) -> DeduplicationSet:
    deduplication_set.state = getattr(
        request,
        "param",
        DeduplicationSet.State.ENCODED,
    )
    deduplication_set.save(update_fields=["state"])
    return deduplication_set


@pytest.fixture
def second_encoded_set(hde_token: HDEToken, deduplication_set_group_factory, deduplication_set_factory):
    group = deduplication_set_group_factory(system=hde_token.system)
    return deduplication_set_factory(group=group, state=DeduplicationSet.State.ENCODED)


@pytest.fixture
def delay(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.views.export_encodings.delay")


def create_url() -> str:
    return reverse(ENCODINGS_EXPORT_CREATE_VIEW)


def status_url(key: str) -> str:
    return f"{reverse(ENCODINGS_EXPORT_STATUS_VIEW)}?" + urlencode({"key": key})


def create_payload(*sets: DeduplicationSet, **extra) -> dict:
    return {"reference_pk": CO_SLUG, "deduplication_set_ids": [str(s.pk) for s in sets], **extra}


def read_zip(key: str) -> zipfile.ZipFile:
    with get_embeddings_storage().open(key) as fh:
        return zipfile.ZipFile(BytesIO(fh.read()))


def jsonl_lines(archive: zipfile.ZipFile, member: str) -> list[dict]:
    return [json.loads(line) for line in archive.read(member).splitlines()]


@pytest.mark.parametrize(
    "encoded_set",
    [
        DeduplicationSet.State.ENCODED,
        DeduplicationSet.State.DEDUPLICATED,
        DeduplicationSet.State.APPROVED,
    ],
    indirect=True,
)
def test_create_returns_key_and_queues_task(
    api_client: APIClient, hde_token: HDEToken, encoded_set: DeduplicationSet, delay: MagicMock
) -> None:
    response = api_client.post(create_url(), data=create_payload(encoded_set), format="json")
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["state"] == "pending"
    key = data["key"]
    assert re.fullmatch(
        rf"exports/{hde_token.system.pk}/{CO_SLUG}/{CO_SLUG}-\d{{8}}T\d{{6}}Z-[0-9a-f]{{8}}\.npy\.zip",
        key,
    )
    delay.assert_called_once_with(key, CO_SLUG, [str(encoded_set.pk)], EXPORT_FORMAT_NPY)


def test_create_with_jsonl_format(api_client: APIClient, encoded_set: DeduplicationSet, delay: MagicMock) -> None:
    payload = create_payload(encoded_set, format=EXPORT_FORMAT_JSONL)
    response = api_client.post(create_url(), data=payload, format="json")
    assert response.status_code == status.HTTP_202_ACCEPTED
    key = response.json()["key"]
    assert key.endswith(".jsonl.zip")
    delay.assert_called_once_with(key, CO_SLUG, [str(encoded_set.pk)], EXPORT_FORMAT_JSONL)


def test_create_rejects_unknown_format(api_client: APIClient, encoded_set: DeduplicationSet, delay: MagicMock) -> None:
    payload = create_payload(encoded_set, format="parquet")
    response = api_client.post(create_url(), data=payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "format" in response.json()
    delay.assert_not_called()


def test_create_keys_are_versioned(api_client: APIClient, encoded_set: DeduplicationSet, delay: MagicMock) -> None:
    first = api_client.post(create_url(), data=create_payload(encoded_set), format="json").json()["key"]
    second = api_client.post(create_url(), data=create_payload(encoded_set), format="json").json()["key"]
    assert first != second


def test_create_rejects_unknown_sets(api_client: APIClient, encoded_set: DeduplicationSet, delay: MagicMock) -> None:
    payload = {"reference_pk": CO_SLUG, "deduplication_set_ids": [str(encoded_set.pk), str(uuid4())]}
    response = api_client.post(create_url(), data=payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "deduplication_set_ids" in response.json()
    delay.assert_not_called()


def test_create_rejects_other_system_sets(
    another_system_api_client: APIClient, encoded_set: DeduplicationSet, delay: MagicMock
) -> None:
    response = another_system_api_client.post(create_url(), data=create_payload(encoded_set), format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    delay.assert_not_called()


@pytest.mark.parametrize(
    "encoded_set",
    [
        DeduplicationSet.State.READY,
        DeduplicationSet.State.ENCODING_IN_PROGRESS,
        DeduplicationSet.State.ENCODING_FAILED,
    ],
    indirect=True,
)
def test_create_rejects_non_encoded_sets(
    api_client: APIClient, encoded_set: DeduplicationSet, delay: MagicMock
) -> None:
    response = api_client.post(create_url(), data=create_payload(encoded_set), format="json")
    assert response.status_code == status.HTTP_409_CONFLICT
    assert str(encoded_set.pk) in response.json()["detail"]
    delay.assert_not_called()


def test_create_rejects_invalid_reference(
    api_client: APIClient, encoded_set: DeduplicationSet, delay: MagicMock
) -> None:
    payload = {"reference_pk": "bad slug/../", "deduplication_set_ids": [str(encoded_set.pk)]}
    response = api_client.post(create_url(), data=payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "reference_pk" in response.json()
    delay.assert_not_called()


def test_create_unauthorized(anonymous_api_client: APIClient) -> None:
    response = anonymous_api_client.post(create_url(), data={}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_status_pending_when_blob_missing(api_client: APIClient, hde_token: HDEToken) -> None:
    key = build_export_key(hde_token.system.pk, CO_SLUG, EXPORT_FORMAT_NPY)
    response = api_client.get(status_url(key))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"key": key, "state": "pending"}


def test_status_rejects_foreign_keys(api_client: APIClient, hde_token: HDEToken) -> None:
    key = build_export_key(hde_token.system.pk + 1, CO_SLUG, EXPORT_FORMAT_NPY)
    response = api_client.get(status_url(key))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_status_ready_returns_signed_url(api_client: APIClient, hde_token: HDEToken) -> None:
    key = build_export_key(hde_token.system.pk, CO_SLUG, EXPORT_FORMAT_NPY)
    get_embeddings_storage().save(key, ContentFile(b"zip-bytes"))

    response = api_client.get(status_url(key))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["state"] == "ready"
    assert data["key"] == key
    assert key in data["url"]
    assert data["expires_at"]


def test_status_failed_returns_error(api_client: APIClient, hde_token: HDEToken) -> None:
    key = build_export_key(hde_token.system.pk, CO_SLUG, EXPORT_FORMAT_NPY)
    get_embeddings_storage().save(error_key(key), ContentFile(json.dumps({"error": "boom"}).encode()))

    response = api_client.get(status_url(key))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"key": key, "state": "failed", "error": "boom"}


def test_status_unauthorized(anonymous_api_client: APIClient) -> None:
    response = anonymous_api_client.get(status_url("exports/1/x/x.zip"))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_npy_export_builds_matrix_and_index(
    hde_token: HDEToken,
    encoded_set: DeduplicationSet,
    second_encoded_set: DeduplicationSet,
    encoding_factory,
) -> None:
    success_a = encoding_factory(deduplication_set=encoded_set)
    success_b = encoding_factory(deduplication_set=second_encoded_set)
    failed = encoding_factory(
        deduplication_set=second_encoded_set,
        embedding=None,
        embedding_status_code=Encoding.StatusCode.NO_FACE_DETECTED,
    )

    key = build_export_key(hde_token.system.pk, CO_SLUG, EXPORT_FORMAT_NPY)
    result = export_encodings(key, CO_SLUG, [str(encoded_set.pk), str(second_encoded_set.pk)], EXPORT_FORMAT_NPY)
    assert result == {"key": key, "sets": 2, "images": 3}

    archive = read_zip(key)
    assert set(archive.namelist()) == {EMBEDDINGS_MEMBER, INDEX_MEMBER, MANIFEST_MEMBER}

    matrix = np.load(BytesIO(archive.read(EMBEDDINGS_MEMBER)))
    assert matrix.dtype == np.float32
    assert matrix.shape == (2, len(success_a.embedding))

    index = {line["reference_pk"]: line for line in jsonl_lines(archive, INDEX_MEMBER)}
    assert len(index) == 3
    np.testing.assert_allclose(
        matrix[index[success_a.reference_pk]["row"]], np.asarray(success_a.embedding, dtype=np.float32)
    )
    np.testing.assert_allclose(
        matrix[index[success_b.reference_pk]["row"]], np.asarray(success_b.embedding, dtype=np.float32)
    )
    assert index[failed.reference_pk]["row"] is None
    assert index[failed.reference_pk]["status_code"] == Encoding.StatusCode.NO_FACE_DETECTED

    manifest = json.loads(archive.read(MANIFEST_MEMBER))
    assert manifest["format"] == EXPORT_FORMAT_NPY
    assert manifest["dim"] == len(success_a.embedding)
    assert manifest["model_version"]
    assert manifest["total_image_count"] == 3
    assert manifest["total_counts_by_status_code"] == {"200": 2, "412": 1}
    # Sets appear in request order with contiguous row ranges.
    assert [entry["deduplication_set_id"] for entry in manifest["sets"]] == [
        str(encoded_set.pk),
        str(second_encoded_set.pk),
    ]
    assert manifest["sets"][0]["row_range"] == [0, 1]
    assert manifest["sets"][1]["row_range"] == [1, 2]


def test_npy_export_without_successful_embeddings(
    hde_token: HDEToken, encoded_set: DeduplicationSet, encoding_factory
) -> None:
    encoding_factory(
        deduplication_set=encoded_set,
        embedding=None,
        embedding_status_code=Encoding.StatusCode.BAD_IMAGE_QUALITY,
    )
    key = build_export_key(hde_token.system.pk, CO_SLUG, EXPORT_FORMAT_NPY)
    export_encodings(key, CO_SLUG, [str(encoded_set.pk)], EXPORT_FORMAT_NPY)

    archive = read_zip(key)
    assert set(archive.namelist()) == {INDEX_MEMBER, MANIFEST_MEMBER}
    (line,) = jsonl_lines(archive, INDEX_MEMBER)
    assert line["row"] is None
    assert json.loads(archive.read(MANIFEST_MEMBER))["dim"] is None


def test_npy_export_rejects_mixed_models(
    hde_token: HDEToken,
    encoded_set: DeduplicationSet,
    second_encoded_set: DeduplicationSet,
    encoding_factory,
) -> None:
    encoding_factory(deduplication_set=encoded_set)
    encoding_factory(deduplication_set=second_encoded_set)
    encoded_set.group.settings = {"recognition_model": "Facenet512"}
    encoded_set.group.save(update_fields=["settings"])
    second_encoded_set.group.settings = {"recognition_model": "ArcFace"}
    second_encoded_set.group.save(update_fields=["settings"])

    key = build_export_key(hde_token.system.pk, CO_SLUG, EXPORT_FORMAT_NPY)
    with pytest.raises(Exception, match="mixed recognition models"):
        export_encodings(key, CO_SLUG, [str(encoded_set.pk), str(second_encoded_set.pk)], EXPORT_FORMAT_NPY)

    storage = get_embeddings_storage()
    assert not storage.exists(key)
    with storage.open(error_key(key)) as fh:
        assert "mixed recognition models" in json.load(fh)["error"]


def test_jsonl_export_builds_single_member(
    hde_token: HDEToken,
    encoded_set: DeduplicationSet,
    second_encoded_set: DeduplicationSet,
    encoding_factory,
) -> None:
    success = encoding_factory(deduplication_set=encoded_set)
    failed = encoding_factory(
        deduplication_set=second_encoded_set,
        embedding=None,
        embedding_status_code=Encoding.StatusCode.NO_FACE_DETECTED,
    )

    key = build_export_key(hde_token.system.pk, CO_SLUG, EXPORT_FORMAT_JSONL)
    result = export_encodings(key, CO_SLUG, [str(encoded_set.pk), str(second_encoded_set.pk)], EXPORT_FORMAT_JSONL)
    assert result == {"key": key, "sets": 2, "images": 2}

    archive = read_zip(key)
    assert set(archive.namelist()) == {ENCODINGS_MEMBER, MANIFEST_MEMBER}

    success_line, failed_line = jsonl_lines(archive, ENCODINGS_MEMBER)
    assert success_line["reference_pk"] == success.reference_pk
    assert success_line["embedding"] == success.embedding
    assert success_line["status_code"] == Encoding.StatusCode.DEDUPLICATE_SUCCESS
    assert success_line["model_version"]
    assert failed_line["reference_pk"] == failed.reference_pk
    assert failed_line["embedding"] is None
    assert failed_line["status_code"] == Encoding.StatusCode.NO_FACE_DETECTED

    manifest = json.loads(archive.read(MANIFEST_MEMBER))
    assert manifest["format"] == EXPORT_FORMAT_JSONL
    assert manifest["total_counts_by_status_code"] == {"200": 1, "412": 1}
    assert manifest["sets"][0]["line_range"] == [0, 1]
    assert manifest["sets"][1]["line_range"] == [1, 2]


def test_export_task_failure_writes_error_blob(
    hde_token: HDEToken, encoded_set: DeduplicationSet, mocker: MockerFixture
) -> None:
    mocker.patch(
        "hope_dedup_engine.apps.api.deduplication.export.DeduplicationSetConfig.from_deduplication_set",
        side_effect=RuntimeError("boom"),
    )
    key = build_export_key(hde_token.system.pk, CO_SLUG, EXPORT_FORMAT_NPY)

    with pytest.raises(RuntimeError):
        export_encodings(key, CO_SLUG, [str(encoded_set.pk)], EXPORT_FORMAT_NPY)

    storage = get_embeddings_storage()
    assert not storage.exists(key)
    with storage.open(error_key(key)) as fh:
        payload = json.load(fh)
    assert "boom" in payload["error"]


def test_key_prefix_matches_build_export_key(hde_token: HDEToken) -> None:
    key = build_export_key(hde_token.system.pk, CO_SLUG, EXPORT_FORMAT_NPY)
    assert key.startswith(export_key_prefix(hde_token.system.pk))
