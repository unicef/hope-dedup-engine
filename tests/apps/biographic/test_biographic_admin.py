import pytest
from django.contrib.messages import SUCCESS, WARNING, get_messages
from django.urls import reverse
from testutils.factories.biographic import (
    BiographicFindingFactory,
    BiographicGroupFactory,
    BiographicJobFactory,
    BiographicRecordFactory,
    BiographicSetFactory,
)
from testutils.factories.user import SuperUserFactory

from hope_dedup_engine.apps.biographic.admin import MARKED_FAILED_ERROR
from hope_dedup_engine.apps.biographic.models import BiographicSet

pytestmark = pytest.mark.django_db

State = BiographicSet.State


@pytest.fixture
def app(django_app_factory, mocked_responses):
    django_app = django_app_factory(csrf_checks=False)
    django_app.set_user(SuperUserFactory(username="superuser"))
    return django_app


def confirm(app, url: str):
    return app.get(url).forms[1].submit().follow()


def button_url(name: str, dataset: BiographicSet) -> str:
    return reverse(f"admin:biographic_biographicset_{name}", args=[dataset.pk])


def test_unlock_processing_releases_the_programs_lock(app):
    dataset = BiographicSetFactory(group=BiographicGroupFactory(processing_locked=True), state=State.DEDUPLICATED)

    confirm(app, button_url("release_processing_lock", dataset))

    dataset.group.refresh_from_db()
    assert dataset.group.processing_locked is False


@pytest.mark.parametrize("state", [State.INDEXING, State.INDEXED, State.DEDUPLICATING])
def test_a_stuck_set_can_be_marked_failed_and_then_retried(app, state):
    dataset = BiographicSetFactory(group=BiographicGroupFactory(processing_locked=True), state=state)

    confirm(app, button_url("mark_failed", dataset))

    dataset.refresh_from_db()
    assert dataset.state == State.FAILED
    assert dataset.error == MARKED_FAILED_ERROR
    assert dataset.group.processing_locked is False
    assert State.INDEXING in BiographicSet.VALID_TRANSITIONS[dataset.state]


def test_group_admin_edits_the_programs_thresholds(app):
    group = BiographicGroupFactory(settings={"duplicate_score": 6.0, "max_hits": 100})
    page = app.get(reverse("admin:biographic_biographicgroup_change", args=[group.pk]))
    form = page.forms[1]
    assert form["duplicate_score"].value == "6.0"
    assert "business_area" not in form.fields

    form["duplicate_score"] = "8.5"
    form["max_hits"] = "40"
    form.submit().follow()

    group.refresh_from_db()
    assert group.settings == {"duplicate_score": 8.5, "max_hits": 40}


def test_set_admin_renders_the_run_log(app):
    dataset = BiographicSetFactory(
        state=State.DEDUPLICATED,
        log=[{"timestamp": "2026-10-13T10:00:00+00:00", "action": "deduplicate", "state": "Deduplicated"}],
    )
    page = app.get(reverse("admin:biographic_biographicset_change", args=[dataset.pk]))
    assert "deduplicate" in page.text


@pytest.mark.parametrize(
    ("dataset_kwargs", "message", "level"),
    [
        ({"notification_url": "https://hope.example.org/cb/", "notify": False}, "Notification sent.", SUCCESS),
        ({"notification_url": None}, "No notification URL configured.", WARNING),
    ],
)
def test_send_notification_button_forces_a_ping(admin_client, mocked_responses, dataset_kwargs, message, level):
    dataset = BiographicSetFactory(state=State.DEDUPLICATED, **dataset_kwargs)
    if dataset.notification_url:
        mocked_responses.add(mocked_responses.GET, dataset.notification_url, status=200)

    response = admin_client.get(button_url("send_notification", dataset))

    (sent,) = get_messages(response.wsgi_request)
    assert (sent.message, sent.level) == (message, level)
    assert len(mocked_responses.calls) == (1 if dataset.notification_url else 0)


def test_job_admin_lists_the_jobs(app):
    job = BiographicJobFactory()
    page = app.get(reverse("admin:biographic_biographicjob_changelist"))
    assert str(job.dataset_id) in page.text
    assert app.get(reverse("admin:biographic_biographicjob_change", args=[job.pk])).status_code == 200


def test_record_admin_renders_the_payload(app):
    record = BiographicRecordFactory(payload={"full_name": "Maria Gonzalez"})
    page = app.get(reverse("admin:biographic_biographicrecord_change", args=[record.pk]))
    assert "Maria Gonzalez" in page.text


def test_record_admin_searches_by_name(app):
    BiographicRecordFactory(payload={"full_name": "Maria Gonzalez"}, full_name="Maria Gonzalez")
    BiographicRecordFactory(payload={"full_name": "Ahmad Shah"}, full_name="Ahmad Shah")
    page = app.get(reverse("admin:biographic_biographicrecord_changelist"), {"q": "Gonzalez"})
    assert "Maria Gonzalez" in page.text
    assert "Ahmad Shah" not in page.text


@pytest.fixture
def two_programs():
    """Two programs with two sets each, one record and one finding per set."""
    sets = {}
    for program in ("alpha", "beta"):
        group = BiographicGroupFactory(program_code=program)
        for n in (1, 2):
            dataset = BiographicSetFactory(group=group)
            record = BiographicRecordFactory(dataset=dataset, reference_pk=f"{program}-{n}")
            BiographicFindingFactory(record=record, matched_reference_pk=f"{program}-match-{n}")
            sets[f"{program}-{n}"] = dataset
    return sets


def listed(page, two_programs) -> set[str]:
    """Which records are on the page. Both changelists show the record's reference_pk."""
    return {key for key in two_programs if f">{key}<" in page.text}


@pytest.mark.parametrize("model", ["biographicrecord", "biographicfinding"])
def test_records_and_findings_filter_by_group_and_set(app, two_programs, model):
    url = reverse(f"admin:biographic_{model}_changelist")
    alpha_1 = two_programs["alpha-1"]

    by_group = app.get(url, {"dataset__group__exact": alpha_1.group_id})
    by_set = app.get(url, {"dataset__group__exact": alpha_1.group_id, "dataset__exact": alpha_1.pk})

    assert listed(by_group, two_programs) == {"alpha-1", "alpha-2"}
    assert listed(by_set, two_programs) == {"alpha-1"}


def test_sets_filter_by_group(app, two_programs):
    alpha = two_programs["alpha-1"].group
    page = app.get(reverse("admin:biographic_biographicset_changelist"), {"group__exact": alpha.pk})
    shown = {key for key, dataset in two_programs.items() if f"/biographicset/{dataset.pk}/change/" in page.text}
    assert shown == {"alpha-1", "alpha-2"}


@pytest.mark.parametrize("term", ["Amina", "Yusuf", "Amina Yusuf"])
def test_record_and_finding_admins_search_given_family_and_full_name(app, term):
    record = BiographicRecordFactory(
        reference_pk="cw-amina",
        payload={"given_name": "Amina", "family_name": "Yusuf"},
        full_name="Amina Yusuf" if " " in term else "",
    )
    BiographicFindingFactory(record=record, matched_reference_pk="old-amina")
    other = BiographicRecordFactory(reference_pk="cw-other", payload={"given_name": "Omar", "family_name": "Shah"})
    BiographicFindingFactory(record=other, matched_reference_pk="old-other")

    records = app.get(reverse("admin:biographic_biographicrecord_changelist"), {"q": term})
    findings = app.get(reverse("admin:biographic_biographicfinding_changelist"), {"q": term})

    assert "cw-amina" in records.text
    assert "cw-other" not in records.text
    assert "old-amina" in findings.text
    assert "old-other" not in findings.text


def test_finding_admin_searches_the_matched_full_name(app):
    for matched_pk, matched_name in (("old-maria", "Maria Gonzalez"), ("old-ahmad", "Ahmad Shah")):
        BiographicFindingFactory(
            record__payload={"given_name": "Omar", "family_name": "Khan"},
            matched_reference_pk=matched_pk,
            matched_full_name=matched_name,
        )
    page = app.get(reverse("admin:biographic_biographicfinding_changelist"), {"q": "Gonzalez"})
    assert "old-maria" in page.text
    assert "old-ahmad" not in page.text


def test_group_admin_lists_its_sets(app, two_programs):
    alpha = two_programs["alpha-1"].group
    page = app.get(reverse("admin:biographic_biographicgroup_change", args=[alpha.pk]))
    for key, dataset in two_programs.items():
        link = reverse("admin:biographic_biographicset_change", args=[dataset.pk])
        assert (link in page.text) == key.startswith("alpha")


@pytest.mark.parametrize("target", ["records", "findings"])
def test_group_buttons_open_the_groups_records_and_findings(app, two_programs, target):
    alpha = two_programs["alpha-1"].group
    page = app.get(reverse(f"admin:biographic_biographicgroup_{target}", args=[alpha.pk])).follow()
    assert f"dataset__group__exact={alpha.pk}" in page.request.url
    assert listed(page, two_programs) == {"alpha-1", "alpha-2"}


@pytest.mark.parametrize("target", ["records", "findings"])
def test_set_buttons_open_the_sets_records_and_findings(app, two_programs, target):
    dataset = two_programs["alpha-1"]
    page = app.get(button_url(target, dataset)).follow()
    assert f"dataset__exact={dataset.pk}" in page.request.url
    assert listed(page, two_programs) == {"alpha-1"}
