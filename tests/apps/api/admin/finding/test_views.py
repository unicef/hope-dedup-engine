from io import BytesIO
from unittest.mock import MagicMock

import pytest
from django.urls import reverse
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.models import Encoding

pytestmark = pytest.mark.django_db


@pytest.fixture
def finding_image_storage(mocker: MockerFixture) -> MagicMock:
    storage = MagicMock()
    storages_mock = mocker.patch("hope_dedup_engine.apps.api.admin.finding.views.storages")
    storages_mock.__getitem__.return_value = storage
    return storage


# ---------- FindingImageView ----------


def test_finding_image_requires_staff(client: MagicMock) -> None:
    url = reverse("admin:api_finding_image", kwargs={"filename": "image.jpg"})

    response = client.get(url)

    assert response.status_code in (301, 302)
    assert "/admin/login" in response.headers.get("Location", "")


def test_finding_image_serves_file(
    admin_client: MagicMock,
    finding_image_storage: MagicMock,
) -> None:
    filename = "hope/abc/image.jpg"
    url = reverse("admin:api_finding_image", kwargs={"filename": filename})
    finding_image_storage.open.return_value = BytesIO(b"image-bytes")

    response = admin_client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("image/")

    cd = response["Content-Disposition"]
    assert "inline;" in cd
    assert 'filename="image.jpg"' in cd

    body = b"".join(response.streaming_content)
    assert body == b"image-bytes"


def test_finding_image_missing_returns_404(
    admin_client: MagicMock,
    finding_image_storage: MagicMock,
) -> None:
    url = reverse("admin:api_finding_image", kwargs={"filename": "missing.jpg"})
    finding_image_storage.open.side_effect = FileNotFoundError("missing")

    response = admin_client.get(url)

    assert response.status_code == 404


# ---------- FindingPreviewView ----------


def test_finding_preview_requires_staff(client: MagicMock, finding: MagicMock) -> None:
    url = reverse("admin:api_finding_details", kwargs={"pk": finding.pk})

    res = client.get(url)

    assert res.status_code in (301, 302)
    assert "/admin/login" in res.headers.get("Location", "")


@pytest.mark.parametrize(
    ("first_filename", "second_filename"),
    [
        ("hope/ds-1/first.jpg", ""),
        ("hope/ds-1/first.jpg", "hope/ds-1/second.jpg"),
    ],
)
def test_finding_preview_context(
    admin_client,
    finding_factory,
    encoding_factory,
    deduplication_set,
    first_filename: str,
    second_filename: str,
) -> None:
    first_encoding = encoding_factory(deduplication_set=deduplication_set, filename=first_filename)
    second_encoding = (
        encoding_factory(deduplication_set=deduplication_set, filename=second_filename) if second_filename else None
    )
    finding = finding_factory(
        deduplication_set=deduplication_set,
        first_encoding=first_encoding,
        second_encoding=second_encoding,
    )

    url = reverse("admin:api_finding_details", kwargs={"pk": finding.pk})
    res = admin_client.get(url)
    assert res.status_code == 200

    ctx = res.context
    assert ctx["finding"].pk == finding.pk
    assert ctx["status_label"] == Encoding.StatusCode(finding.status_code).label

    assert ctx["first_image_url"] == reverse("admin:api_finding_image", kwargs={"filename": first_filename})

    if second_filename:
        assert ctx["second_image_url"] == reverse("admin:api_finding_image", kwargs={"filename": second_filename})
    else:
        assert ctx["second_image_url"] is None
