from io import BytesIO
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from azure.core.exceptions import ResourceNotFoundError
from storages.backends.azure_storage import AzureStorage
from django.urls import reverse
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.apps.api.models import Encoding

pytestmark = pytest.mark.django_db


@pytest.fixture
def finding_image_storage(mocker: MockerFixture) -> AzureStorage:
    storage = MagicMock(spec=AzureStorage)
    manager = ImagesStorageManager()
    manager.storage = storage
    mocker.patch(
        "hope_dedup_engine.apps.api.admin.views.ImagesStorageManager",
        return_value=manager,
    )
    return storage


# ---------- FindingImageView ----------


def test_finding_image_requires_staff(client: MagicMock) -> None:
    url = reverse("finding-image", kwargs={"filename": "image.jpg"})

    response = client.get(url)

    assert response.status_code in (301, 302)
    assert "/admin/login" in response.headers.get("Location", "")


def test_finding_image_serves_file(
    admin_client: MagicMock,
    finding_image_storage: AzureStorage,
) -> None:
    filename = "image.jpg"
    url = reverse("finding-image", kwargs={"filename": filename})
    finding_image_storage.open.return_value = BytesIO(b"image-bytes")

    response = admin_client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("image/")

    cd = response["Content-Disposition"]
    assert "inline;" in cd
    assert f'filename="{filename}"' in cd

    body = b"".join(response.streaming_content)
    assert body == b"image-bytes"


def test_finding_image_missing_returns_404(
    admin_client: MagicMock,
    finding_image_storage: AzureStorage,
) -> None:
    url = reverse("finding-image", kwargs={"filename": "missing.jpg"})
    finding_image_storage.open.side_effect = ResourceNotFoundError("missing")
    response = admin_client.get(url)
    assert response.status_code == 404


# ---------- FindingPreviewView ----------


def test_finding_preview_requires_staff(client: MagicMock, finding: MagicMock) -> None:
    url = reverse("finding-preview", kwargs={"pk": finding.pk})

    res = client.get(url)

    assert res.status_code in (301, 302)
    assert "/admin/login" in res.headers.get("Location", "")


@pytest.mark.parametrize(
    ("first_filename", "second_filename"),
    [
        ("first.jpg", ""),
        ("first.jpg", "second.jpg"),
    ],
)
def test_finding_preview_context(
    admin_client,
    finding,
    first_filename,
    second_filename,
) -> None:
    finding.first_filename = first_filename
    finding.second_filename = second_filename
    finding.save(update_fields=["first_filename", "second_filename"])
    url = reverse("finding-preview", kwargs={"pk": finding.pk})

    res = admin_client.get(url)
    assert res.status_code == 200

    ctx = res.context
    assert ctx["finding"].pk == finding.pk
    assert ctx["status_label"] == Encoding.StatusCode(finding.status_code).label
    assert ctx["first_image_url"] == reverse("finding-image", kwargs={"filename": first_filename})
    if second_filename:
        assert ctx["second_image_url"] == reverse("finding-image", kwargs={"filename": second_filename})
    else:
        assert ctx["second_image_url"] is None
