import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from hope_dedup_engine.apps.security.models import User
from hope_dedup_engine.apps.api.models import Finding
from testutils.perms import user_grant_permissions


@pytest.fixture
def staff_user(db: pytest.FixtureRequest) -> User:
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="staff",
        is_staff=True,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("perms", "visible"),
    [
        (["api.view_finding"], False),
        (["api.view_finding", "api.view_finding_details"], True),
    ],
    ids=["no_details_permission", "with_details_permission"],
)
def test_finding_details_button_visibility(
    staff_user: User,
    finding: Finding,
    client: Client,
    perms: list[str],
    visible: bool,
) -> None:
    change_url = reverse("admin:api_finding_change", args=[finding.pk])
    preview_url = reverse("finding-preview", kwargs={"pk": finding.pk})

    with user_grant_permissions(staff_user, perms):
        client.force_login(staff_user)

        res = client.get(change_url)
        assert res.status_code == 200

        res = client.get(preview_url)
        assert res.status_code == (200 if visible else 404)
