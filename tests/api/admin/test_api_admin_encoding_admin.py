from pytest_mock import MockerFixture

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
