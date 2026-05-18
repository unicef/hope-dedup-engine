import pytest
from django.contrib.admin import AdminSite
from django.test import RequestFactory
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.admin import EncodingAdmin
from hope_dedup_engine.apps.api.admin.encoding.admin import (
    prepare_detection_results,
    Result,
    file_link,
    FILE_LINK,
    prepare_deduplication_results,
    FINDING_DETAILS,
)
from hope_dedup_engine.apps.api.admin.encoding.utils.process import Finding
from hope_dedup_engine.apps.api.models import Encoding


@pytest.mark.parametrize(
    "filename_label, filename, expected",
    [
        (
            "data:image/jpeg;base64,/9j/4AAQ...",
            "data:image/jpeg;base64,/9j/4AAQ...(megabytes)",
            "image/jpeg:<binary-data>",
        ),
        (None, "photos/face.jpg", "photos/face.jpg"),
        ("photos/face.jpg", "ignored", "photos/face.jpg"),
    ],
    ids=[
        "annotation_present_data_url",
        "annotation_missing_falls_back_to_filename",
        "annotation_present_regular_path",
    ],
)
def test_filename_pretty(filename_label: str | None, filename: str, expected: str, mocker: MockerFixture) -> None:
    encoding = mocker.Mock(spec=Encoding, filename=filename)
    if filename_label is not None:
        encoding._filename_label = filename_label
    else:
        del encoding._filename_label
    admin = EncodingAdmin(Encoding, AdminSite())
    assert admin.filename_pretty(encoding) == expected


@pytest.mark.parametrize(
    "scores, expected",
    [
        (None, "N/A"),
        ({}, "N/A"),
        (
            {"Sharpness": 80.0, "DynamicRange": 50.0, "Contrast": 90.0},
            str({"DynamicRange": 50.0, "Sharpness": 80.0, "Contrast": 90.0}),
        ),
        (
            {"Sharpness": 80.0, "DynamicRange": None, "Contrast": 90.0},
            str({"DynamicRange": None, "Sharpness": 80.0, "Contrast": 90.0}),
        ),
        (
            {"Only": 42.0},
            str({"Only": 42.0}),
        ),
        (
            {"A": None, "B": None},
            str({"A": None, "B": None}),
        ),
    ],
    ids=[
        "none_scores",
        "empty_scores",
        "sorted_by_value_ascending",
        "none_values_sorted_first",
        "single_score",
        "all_none_values",
    ],
)
def test_image_quality_scores_sorted(scores: dict | None, expected: str, mocker: MockerFixture) -> None:
    encoding = mocker.Mock(spec=Encoding, image_quality_scores=scores)
    admin = EncodingAdmin(Encoding, AdminSite())
    assert admin.image_quality_scores_sorted(encoding) == expected


def test_prepare_detection_results() -> None:
    assert prepare_detection_results([50, 75, 100], 75) == [
        Result(50, "yes", "+25"),
        Result(75, "yes", "+0"),
        Result(100, "no", "-25"),
    ]


def test_file_link(mocker: MockerFixture) -> None:
    format_html_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.format_html")
    reverse_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.reverse")
    assert file_link(filename := "test") == format_html_mock.return_value
    format_html_mock.assert_called_once_with(FILE_LINK, filename=filename, link=reverse_mock.return_value)


def test_prepare_deduplication_results(mocker: MockerFixture, encoding: Encoding) -> None:
    format_html_join_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.format_html_join")
    file_link_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.file_link")
    assert prepare_deduplication_results(
        [50, 75, 100], [[], [], [Finding(confidence=75, encoding0=encoding, encoding1=encoding)], []]
    ) == [
        Result(50, 0, format_html_join_mock.return_value),
        Result(75, 1, format_html_join_mock.return_value),
        Result(100, 0, format_html_join_mock.return_value),
    ]
    format_html_join_mock.assert_has_calls(
        [
            mocker.call("", FINDING_DETAILS, []),
            mocker.call(
                "",
                FINDING_DETAILS,
                [
                    {
                        "confidence": 75,
                        "filename0": file_link_mock.return_value,
                        "filename1": file_link_mock.return_value,
                    }
                ],
            ),
            mocker.call("", FINDING_DETAILS, []),
        ]
    )
    file_link_mock.assert_has_calls([mocker.call(encoding.filename), mocker.call(encoding.filename)])


def test_encoding_admin_detect_face_initial(mocker: MockerFixture, rf: RequestFactory, admin_user, encoding) -> None:
    request = rf.post(f"/admin/api/encoding/{encoding.pk}/detect_face/")
    request.user = admin_user
    admin_site = AdminSite()

    find_face_form_class_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.FindFaceForm")
    render_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.render")
    format_html_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.format_html")

    encoding_admin = EncodingAdmin(Encoding, admin_site)
    expected_context = {
        "page_title": f"Detect face on {encoding.filename}",
        "title": f"Detect face on {encoding.filename}",
        "opts": Encoding._meta,
        "encoding": encoding,
        "value_title": "Face detected",
        "button_title": "Detect face",
        "details_title": "Confidence delta",
        "extra": format_html_mock.return_value,
        "form": find_face_form_class_mock.return_value,
    }

    encoding_admin.detect_face(encoding_admin, request, encoding.pk)

    find_face_form_class_mock.assert_called_once_with()
    render_mock.assert_called_once_with(request, "admin/api/encoding/threshold_results.html", context=expected_context)


def test_encoding_admin_detect_face_submit(mocker: MockerFixture, rf: RequestFactory, admin_user, encoding) -> None:
    request = rf.post(f"/admin/api/encoding/{encoding.pk}/detect_face/", data={"submit": "Detect face"})
    request.user = admin_user
    admin_site = AdminSite()

    find_face_form_class_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.FindFaceForm")
    render_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.render")
    format_html_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.format_html")
    detect_face_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.detect_face")
    calculate_thresholds_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.calculate_thresholds")
    prepare_detection_results_mock = mocker.patch(
        "hope_dedup_engine.apps.api.admin.encoding.admin.prepare_detection_results"
    )

    encoding_admin = EncodingAdmin(Encoding, admin_site)
    expected_context = {
        "page_title": f"Detect face on {encoding.filename}",
        "title": f"Detect face on {encoding.filename}",
        "opts": Encoding._meta,
        "encoding": encoding,
        "value_title": "Face detected",
        "button_title": "Detect face",
        "details_title": "Confidence delta",
        "extra": format_html_mock.return_value,
        "form": find_face_form_class_mock.return_value,
        "results": prepare_detection_results_mock.return_value,
    }

    encoding_admin.detect_face(encoding_admin, request, encoding.pk)

    find_face_form_class_mock.assert_called_once_with(request.POST)
    render_mock.assert_called_once_with(request, "admin/api/encoding/threshold_results.html", context=expected_context)
    prepare_detection_results_mock.assert_called_once_with(
        calculate_thresholds_mock.return_value, detect_face_mock.return_value.confidence
    )


def test_encoding_admin_deduplicate_selected_encodings_initial(
    mocker: MockerFixture, rf: RequestFactory, admin_user
) -> None:
    request = rf.post("/admin/api/encoding/", data={"action": "action", "_selected_action": "selected_action"})
    request.user = admin_user
    admin_site = AdminSite()

    deduplicate_form_class_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.DeduplicateForm")
    render_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.render")
    queryset_mock = mocker.Mock()

    encoding_admin = EncodingAdmin(Encoding, admin_site)
    expected_context = {
        "page_title": "Deduplicate selected encodings",
        "value_title": "Duplicate count",
        "button_title": "Deduplicate",
        "details_title": "Duplicates",
        "form": deduplicate_form_class_mock.return_value,
    }

    encoding_admin.deduplicate_selected_encodings(request, queryset_mock)

    deduplicate_form_class_mock.assert_called_once_with(
        initial={"action": "action", "_selected_action": ["selected_action"]}
    )
    render_mock.assert_called_once_with(request, "admin/api/encoding/threshold_results.html", context=expected_context)


def test_encoding_admin_deduplicate_selected_encodings_submit(
    mocker: MockerFixture, rf: RequestFactory, admin_user, encoding
) -> None:
    request = rf.post(
        "/admin/api/encoding/",
        data={"action": "action", "_selected_action": "selected_action", "submit": "Deduplicate"},
    )
    request.user = admin_user
    admin_site = AdminSite()

    deduplicate_form_class_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.DeduplicateForm")
    render_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.render")
    mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.deduplicate")
    group_by_thresholds_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.group_by_thresholds")
    calculate_thresholds_mock = mocker.patch("hope_dedup_engine.apps.api.admin.encoding.admin.calculate_thresholds")
    prepare_deduplication_results_mock = mocker.patch(
        "hope_dedup_engine.apps.api.admin.encoding.admin.prepare_deduplication_results"
    )
    queryset_mock = mocker.Mock()

    encoding_admin = EncodingAdmin(Encoding, admin_site)
    expected_context = {
        "page_title": "Deduplicate selected encodings",
        "value_title": "Duplicate count",
        "button_title": "Deduplicate",
        "details_title": "Duplicates",
        "form": deduplicate_form_class_mock.return_value,
        "results": prepare_deduplication_results_mock.return_value,
    }

    encoding_admin.deduplicate_selected_encodings(request, queryset_mock)

    deduplicate_form_class_mock.assert_called_once_with(request.POST)
    render_mock.assert_called_once_with(request, "admin/api/encoding/threshold_results.html", context=expected_context)
    prepare_deduplication_results_mock.assert_called_once_with(
        calculate_thresholds_mock.return_value, group_by_thresholds_mock.return_value
    )
