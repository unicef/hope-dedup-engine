import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from hope_dedup_engine.apps.security.models import User
from hope_dedup_engine.apps.api.models import Finding, DeduplicationSet
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
    ds1 = deduplication_set_factory(state=DeduplicationSet.State.APPROVED)
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
    ("url_name", "clears", "expected_state"),
    [
        ("admin:api_deduplicationset_clear_embeddings", True, DeduplicationSet.State.READY),
        ("admin:api_deduplicationset_findings_remove", False, DeduplicationSet.State.ENCODED),
    ],
    ids=["clear_embeddings", "findings_remove"],
)
def test_ds_cleanup_buttons(confirm, seeded_ds, url_name, clears, expected_state):
    assert confirm(reverse(url_name, args=[seeded_ds.pk])).status_code == 200
    seeded_ds.refresh_from_db()
    assert seeded_ds.state == expected_state
    assert seeded_ds.finding_set.count() == 0
    assert seeded_ds.encoding_set.filter(embedding__isnull=False).exists() is (not clears)
    assert seeded_ds.encoding_set.filter(embedding_status_code__isnull=False).exists() is (not clears)


def test_ds_encodings_view_redirect(app, seeded_ds) -> None:
    res = app.get(
        reverse("admin:api_deduplicationset_encodings_view", args=[seeded_ds.pk]),
        expect_errors=True,
    )
    assert res.status_code == 302
    expected = reverse(
        "admin:api_encoding_changelist",
        query={"deduplication_set": str(seeded_ds.pk)},
    )
    assert res.location.endswith(expected)


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


def test_ds_encode_blocked_when_locked(confirm, seeded_ds):
    seeded_ds.group.processing_locked = True
    seeded_ds.group.save(update_fields=["processing_locked"])

    assert confirm(reverse("admin:api_deduplicationset_encode", args=[seeded_ds.pk])).status_code == 200

    seeded_ds.refresh_from_db()
    assert seeded_ds.encoding_set.filter(embedding__isnull=False).exists() is True
    assert seeded_ds.finding_set.count() == 1


def test_ds_deduplicate_blocked_when_locked(confirm, seeded_ds):
    seeded_ds.group.processing_locked = True
    seeded_ds.group.save(update_fields=["processing_locked"])

    assert confirm(reverse("admin:api_deduplicationset_deduplicate", args=[seeded_ds.pk])).status_code == 200

    seeded_ds.refresh_from_db()
    assert seeded_ds.encoding_set.filter(embedding__isnull=False).exists() is True
    assert seeded_ds.finding_set.count() == 1


def test_ds_encode(confirm, seeded_ds, mocker):
    create = mocker.patch("hope_dedup_engine.apps.api.admin.deduplicationset.MainJob.objects.create")
    job = mocker.Mock()
    create.return_value = job

    assert confirm(reverse("admin:api_deduplicationset_encode", args=[seeded_ds.pk])).status_code == 200

    seeded_ds.refresh_from_db()
    assert seeded_ds.state == DeduplicationSet.State.ENCODING_IN_PROGRESS
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

    seeded_ds.refresh_from_db()
    assert seeded_ds.state == DeduplicationSet.State.ENCODING_IN_PROGRESS
    assert create.call_args.kwargs["deduplication_set"].pk == seeded_ds.pk
    assert create.call_args.kwargs["encode_only"] is False
    job.queue.assert_called_once_with()

    assert seeded_ds.finding_set.count() == 0
    assert seeded_ds.encoding_set.filter(embedding__isnull=False).exists() is True
    assert seeded_ds.encoding_set.filter(embedding_status_code__isnull=False).exists() is True


@pytest.fixture
def ds_with_constraint_conflict(deduplication_set, encoding, deduplication_set_factory):
    """A dedup set in a non-active state whose group already has an active set (constraint conflict)."""
    deduplication_set.state = DeduplicationSet.State.ENCODING_FAILED
    deduplication_set.save(update_fields=["state"])
    deduplication_set_factory(group=deduplication_set.group, state=DeduplicationSet.State.READY)
    return deduplication_set


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:api_deduplicationset_encode",
        "admin:api_deduplicationset_deduplicate",
    ],
    ids=["encode", "deduplicate"],
)
def test_ds_process_integrity_error_releases_lock(confirm, ds_with_constraint_conflict, url_name, mocker):
    mocker.patch("hope_dedup_engine.apps.api.admin.deduplicationset.MainJob.objects.create")
    ds = ds_with_constraint_conflict

    assert confirm(reverse(url_name, args=[ds.pk])).status_code == 200

    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.ENCODING_FAILED
    ds.group.refresh_from_db()
    assert ds.group.processing_locked is False


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:api_deduplicationset_clear_embeddings",
        "admin:api_deduplicationset_findings_remove",
    ],
    ids=["clear_embeddings", "findings_remove"],
)
def test_ds_cleanup_integrity_error_rolls_back(confirm, ds_with_constraint_conflict, url_name):
    ds = ds_with_constraint_conflict

    assert confirm(reverse(url_name, args=[ds.pk])).status_code == 200

    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.ENCODING_FAILED


# --- DeduplicationSetGroup -----------------------------------------------------------------


def test_group_encodings_view_redirect(app, seeded_group) -> None:
    res = app.get(
        reverse("admin:api_deduplicationsetgroup_encodings", args=[seeded_group.pk]),
        expect_errors=True,
    )
    assert res.status_code == 302

    expected = reverse("admin:api_encoding_changelist") + f"?deduplication_set__group__exact={seeded_group.pk}"
    assert res.location.endswith(expected)


def test_group_findings_view_redirect(app, seeded_group) -> None:
    res = app.get(
        reverse("admin:api_deduplicationsetgroup_findings", args=[seeded_group.pk]),
        expect_errors=True,
    )
    assert res.status_code == 302

    expected = reverse("admin:api_finding_changelist") + f"?deduplication_set__group__exact={seeded_group.pk}"
    assert res.location.endswith(expected)


@pytest.fixture
def locked_group(seeded_group):
    seeded_group.processing_locked = True
    seeded_group.save(update_fields=["processing_locked"])
    return seeded_group


def test_group_release_processing_lock_asks_confirmation(app, locked_group) -> None:
    url = reverse("admin:api_deduplicationsetgroup_release_processing_lock", args=[locked_group.pk])

    res = app.get(url, expect_errors=True)

    assert res.status_code == 200
    locked_group.refresh_from_db()
    assert locked_group.processing_locked is True


def test_group_release_processing_lock(confirm, locked_group) -> None:
    url = reverse("admin:api_deduplicationsetgroup_release_processing_lock", args=[locked_group.pk])

    assert confirm(url).status_code == 200

    locked_group.refresh_from_db()
    assert locked_group.processing_locked is False
