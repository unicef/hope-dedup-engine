import pytest
from django.contrib.admin import AdminSite
from django.test import RequestFactory

from hope_dedup_engine.apps.api.admin.deduplicationset import DeduplicationSetAdmin
from hope_dedup_engine.apps.api.admin.deduplicationsetgroup import DeduplicationSetGroupAdmin
from hope_dedup_engine.apps.api.admin.encoding.admin import EncodingAdmin
from hope_dedup_engine.apps.api.admin.finding.admin import FindingAdmin
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding, Finding
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup


pytestmark = pytest.mark.django_db


def test_admin_querysets_exclude_soft_deleted_group(
    rf: RequestFactory,
    admin_user,
    deduplication_set_group_factory,
    deduplication_set_factory,
    encoding_factory,
    finding_factory,
) -> None:
    active_group = deduplication_set_group_factory()
    deleted_group = deduplication_set_group_factory(deleted=True)

    active_ds = deduplication_set_factory(group=active_group)
    deleted_ds = deduplication_set_factory(group=deleted_group)

    active_encoding = encoding_factory(deduplication_set=active_ds)
    deleted_encoding = encoding_factory(deduplication_set=deleted_ds)

    active_finding = finding_factory(
        deduplication_set=active_ds,
        first_encoding=active_encoding,
        second_encoding=None,
    )
    deleted_finding = finding_factory(
        deduplication_set=deleted_ds,
        first_encoding=deleted_encoding,
        second_encoding=None,
    )

    request = rf.get("/admin/")
    request.user = admin_user
    site = AdminSite()

    group_qs = DeduplicationSetGroupAdmin(DeduplicationSetGroup, site).get_queryset(request)
    assert group_qs.filter(pk=active_group.pk).exists()
    assert not group_qs.filter(pk=deleted_group.pk).exists()

    ds_qs = DeduplicationSetAdmin(DeduplicationSet, site).get_queryset(request)
    assert ds_qs.filter(pk=active_ds.pk).exists()
    assert not ds_qs.filter(pk=deleted_ds.pk).exists()

    encoding_qs = EncodingAdmin(Encoding, site).get_queryset(request)
    assert encoding_qs.filter(pk=active_encoding.pk).exists()
    assert not encoding_qs.filter(pk=deleted_encoding.pk).exists()

    finding_qs = FindingAdmin(Finding, site).get_queryset(request)
    assert finding_qs.filter(pk=active_finding.pk).exists()
    assert not finding_qs.filter(pk=deleted_finding.pk).exists()


def test_group_admin_disables_hard_delete(rf: RequestFactory, admin_user) -> None:
    request = rf.get("/admin/")
    request.user = admin_user

    model_admin = DeduplicationSetGroupAdmin(DeduplicationSetGroup, AdminSite())

    assert model_admin.has_delete_permission(request) is False
