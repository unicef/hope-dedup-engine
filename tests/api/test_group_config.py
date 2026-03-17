import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig, get_default_group_settings
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup

URL_NAME = "deduplication_set_group_config"
JSON = "json"


def config_url(reference_pk: str) -> str:
    return reverse(URL_NAME, kwargs={"reference_pk": reference_pk})


@pytest.mark.django_db
def test_get_returns_defaults_when_group_does_not_exist(api_client: APIClient):
    response = api_client.get(config_url("nonexistent-ref"))
    assert response.status_code == status.HTTP_200_OK
    api_field_names = [f.name for f in DeduplicationSetConfig.setting_fields(api=True)]
    assert set(response.json().keys()) == set(api_field_names)


@pytest.mark.django_db
def test_get_returns_group_settings(api_client: APIClient, hde_token, deduplication_set_group_factory):
    group = deduplication_set_group_factory(system=hde_token.system)
    group.settings = get_default_group_settings()
    group.settings["face_detection_confidence_threshold"] = 0.75
    group.settings["sharpness_threshold"] = 0.5
    group.save()

    response = api_client.get(config_url(group.reference_pk))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["face_detection_confidence_threshold"] == 0.75
    assert data["sharpness_threshold"] == 0.5


@pytest.mark.django_db
def test_get_anonymous_is_rejected(anonymous_api_client: APIClient):
    response = anonymous_api_client.get(config_url("any-ref"))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_another_system_does_not_see_group(
    another_system_api_client: APIClient, hde_token, deduplication_set_group_factory
):
    group = deduplication_set_group_factory(system=hde_token.system)
    group.settings = get_default_group_settings()
    group.settings["sharpness_threshold"] = 0.9
    group.save()

    response = another_system_api_client.get(config_url(group.reference_pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["sharpness_threshold"] != 0.9


@pytest.mark.django_db
def test_post_creates_group_with_settings(api_client: APIClient, hde_token):
    ref_pk = "new-group-ref"
    payload = {"sharpness_threshold": 0.6, "eyes_open_threshold": 0.7}
    response = api_client.post(config_url(ref_pk), data=payload, format=JSON)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["sharpness_threshold"] == 0.6
    assert data["eyes_open_threshold"] == 0.7

    group = DeduplicationSetGroup.objects.get(reference_pk=ref_pk, system=hde_token.system)
    assert group.settings["sharpness_threshold"] == 0.6


@pytest.mark.django_db
def test_post_updates_existing_group(api_client: APIClient, hde_token, deduplication_set_group_factory):
    group = deduplication_set_group_factory(system=hde_token.system)
    group.settings = get_default_group_settings()
    group.save()

    payload = {"duplicate_confidence_threshold": 0.8}
    response = api_client.post(config_url(group.reference_pk), data=payload, format=JSON)

    assert response.status_code == status.HTTP_200_OK
    group.refresh_from_db()
    assert group.settings["duplicate_confidence_threshold"] == 0.8


@pytest.mark.django_db
def test_post_rejects_out_of_range_value(api_client: APIClient):
    response = api_client.post(config_url("any-ref"), data={"sharpness_threshold": 1.5}, format=JSON)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_post_anonymous_is_rejected(anonymous_api_client: APIClient):
    response = anonymous_api_client.post(config_url("any-ref"), data={"sharpness_threshold": 0.5}, format=JSON)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
