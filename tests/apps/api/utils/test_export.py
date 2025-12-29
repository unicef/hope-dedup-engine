import csv
import io
import pytest

from collections.abc import Iterable
from typing import Any
from pytest_mock import MockerFixture
from django.http import StreamingHttpResponse
from django.utils.http import content_disposition_header

from hope_dedup_engine.apps.api.utils.export import DEFAULT_FINDING_FIELDS, export_as_csv


@pytest.fixture
def qs(mocker: MockerFixture) -> Any:
    def _make(rows: Iterable[tuple[Any, ...]]) -> Any:
        q = mocker.MagicMock()
        q.values_list.return_value.iterator.return_value = iter(rows)
        return q

    return _make


def csv_rows(resp: StreamingHttpResponse) -> list[list[str]]:
    text = "".join(
        chunk.decode() if isinstance(chunk, (bytes, bytearray)) else chunk for chunk in resp.streaming_content
    )
    return list(csv.reader(io.StringIO(text)))


def test_export_as_csv_defaults(qs: Any) -> None:
    filename = "a.csv"
    data_rows = [(1, "r1", None, 0.9, "OK")]
    expected_rows = [list(DEFAULT_FINDING_FIELDS), ["1", "r1", "", "0.9", "OK"]]

    resp = export_as_csv(qs(data_rows), filename)

    assert resp.headers["Content-Disposition"] == content_disposition_header(True, filename)
    assert csv_rows(resp) == expected_rows


def test_export_as_csv_custom(qs) -> None:
    filename = "b.csv"
    data_rows = [(1,)]
    expected_rows = [["ID"], ["1"]]

    resp = export_as_csv(qs(data_rows), filename, fields=("pk",), headers=("ID",), chunk_size=7)

    assert csv_rows(resp) == expected_rows


@pytest.mark.parametrize("filename", ["x y.csv", "отчёт.csv"], ids=["spaces", "unicode"])
def test_export_as_csv_disposition_escaping(qs, filename: str) -> None:
    resp = export_as_csv(qs([]), filename)

    assert resp.headers["Content-Disposition"] == content_disposition_header(True, filename)
