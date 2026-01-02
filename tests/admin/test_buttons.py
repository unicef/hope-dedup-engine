import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from hope_dedup_engine.apps.security.models import User
from hope_dedup_engine.apps.api.models import Finding
from testutils.perms import user_grant_permissions
from testutils.factories.user import SuperUserFactory


pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user(db: pytest.FixtureRequest) -> User:
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="staff",
        is_staff=True,
    )


@pytest.fixture
def app(django_app_factory, mocked_responses):
    django_app = django_app_factory(csrf_checks=False)
    admin_user = SuperUserFactory(username="superuser")
    django_app.set_user(admin_user)
    django_app._user = admin_user
    return django_app


@pytest.fixture
def confirm(app):
    return lambda url: app.get(url, expect_errors=True).forms[1].submit().follow()


@pytest.fixture
def seeded_ds(deduplication_set_factory, encoding_factory, finding_factory):
    """DeduplicationSet with two encodings: one has embedding, one has status_code; plus one finding."""
    ds = deduplication_set_factory()
    e1 = encoding_factory(deduplication_set=ds)
    e2 = encoding_factory(deduplication_set=ds)
    m = e1.__class__
    m.objects.filter(pk=e1.pk).update(embedding=[0.1], embedding_status_code=None)
    m.objects.filter(pk=e2.pk).update(embedding=None, embedding_status_code=200)
    finding_factory(deduplication_set=ds)
    return ds


@pytest.fixture
def seeded_group(deduplication_set_factory, encoding_factory, finding_factory):
    """Group with 2 sets; each set has (1 embedding) + (1 status_code) + (1 finding)."""
    ds1 = deduplication_set_factory()
    group = ds1.group
    ds2 = deduplication_set_factory(group=group)

    for ds in (ds1, ds2):
        e1 = encoding_factory(deduplication_set=ds)
        e2 = encoding_factory(deduplication_set=ds)
        m = e1.__class__
        m.objects.filter(pk=e1.pk).update(embedding=[0.1], embedding_status_code=None)
        m.objects.filter(pk=e2.pk).update(embedding=None, embedding_status_code=200)
        finding_factory(deduplication_set=ds)

    return group


# --- Finding -----------------------------------------------------------------


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
    preview_url = reverse("admin:api_finding_details", kwargs={"pk": finding.pk})

    with user_grant_permissions(staff_user, perms):
        client.force_login(staff_user)

        res = client.get(change_url)
        assert res.status_code == 200

        res = client.get(preview_url)
        assert res.status_code == (200 if visible else 403)


# --- DeduplicationSet -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("url_name", "clears"),
    [
        ("admin:api_deduplicationset_clear_embeddings", True),
        ("admin:api_deduplicationset_findings_remove", False),
    ],
    ids=["clear_embeddings", "findings_remove"],
)
def test_ds_cleanup_buttons(confirm, seeded_ds, url_name, clears):
    assert confirm(reverse(url_name, args=[seeded_ds.pk])).status_code == 200
    assert seeded_ds.finding_set.count() == 0
    assert seeded_ds.encoding_set.filter(embedding__isnull=False).exists() is (not clears)
    assert seeded_ds.encoding_set.filter(embedding_status_code__isnull=False).exists() is (not clears)


def test_ds_findings_view_redirect(app, seeded_ds) -> None:
    res = app.get(reverse("admin:api_deduplicationset_findings_view", args=[seeded_ds.pk]), expect_errors=True)
    assert res.status_code == 302

    expected = reverse("admin:api_finding_changelist", query={"deduplication_set": str(seeded_ds.pk)})
    assert res.location.endswith(expected)


def test_ds_findings_export_csv(app, seeded_ds) -> None:
    res = app.get(reverse("admin:api_deduplicationset_findings_export", args=[seeded_ds.pk]), expect_errors=True)
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("text/csv")
    assert res.headers["Content-Disposition"].startswith("attachment;")
    assert "findings.csv" in res.headers["Content-Disposition"]


def test_ds_encode(confirm, seeded_ds, mocker):
    create = mocker.patch("hope_dedup_engine.apps.api.admin.deduplicationset.MainJob.objects.create")
    job = mocker.Mock()
    create.return_value = job

    assert confirm(reverse("admin:api_deduplicationset_encode", args=[seeded_ds.pk])).status_code == 200

    assert create.call_args.kwargs["deduplication_set"].pk == seeded_ds.pk
    assert create.call_args.kwargs["encode_only"] is True
    job.queue.assert_called_once_with()

    assert seeded_ds.finding_set.count() == 0
    assert seeded_ds.encoding_set.filter(embedding__isnull=False).exists() is False
    assert seeded_ds.encoding_set.filter(embedding_status_code__isnull=False).exists() is False


def test_ds_deduplicate(confirm, seeded_ds, mocker):
    create = mocker.patch("hope_dedup_engine.apps.api.admin.deduplicationset.MainJob.objects.create")
    job = mocker.Mock()
    create.return_value = job

    assert confirm(reverse("admin:api_deduplicationset_deduplicate", args=[seeded_ds.pk])).status_code == 200

    assert create.call_args.kwargs["deduplication_set"].pk == seeded_ds.pk
    assert "encode_only" not in create.call_args.kwargs
    job.queue.assert_called_once_with()

    assert seeded_ds.finding_set.count() == 1
    assert seeded_ds.encoding_set.filter(embedding__isnull=False).exists() is True
    assert seeded_ds.encoding_set.filter(embedding_status_code__isnull=False).exists() is True


# --- DeduplicationSetGroup -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("url_name", "clears"),
    [
        ("admin:api_deduplicationsetgroup_clear_embeddings", True),
        ("admin:api_deduplicationsetgroup_remove_findings", False),
    ],
    ids=["group_clear_embeddings", "group_remove_findings"],
)
def test_group_cleanup_buttons(confirm, seeded_group, url_name, clears):
    assert confirm(reverse(url_name, args=[seeded_group.pk])).status_code == 200

    for ds in seeded_group.deduplicationset_set.all():
        assert ds.finding_set.count() == 0
        assert ds.encoding_set.filter(embedding__isnull=False).exists() is (not clears)
        assert ds.encoding_set.filter(embedding_status_code__isnull=False).exists() is (not clears)
