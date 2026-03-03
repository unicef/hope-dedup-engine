import csv
import io

import pytest
from django.utils.http import content_disposition_header
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.utils.export import stream_as_csv

FIELDS = ("c1", "c2", "c3")


@pytest.fixture
def qs(mocker: MockerFixture):
    def _make(rows):
        q = mocker.MagicMock()
        q.values_list.return_value.iterator.return_value = iter(rows)
        return q

    return _make


@pytest.mark.parametrize(
    ("rows", "kwargs", "expected"),
    [
        ([(1, "x", 0.5)], {"fields": FIELDS, "filename": "a.csv"}, [list(FIELDS), ["1", "x", "0.5"]]),
        ([(1,)], {"fields": ("id",), "headers": ("ID",), "chunk_size": 7, "filename": "b.csv"}, [["ID"], ["1"]]),
        (
            [(2,)],
            {
                "fields": ("id",),
                "headers": ("id", "double"),
                "row_mapper": lambda r: (r[0], r[0] * 2),
                "filename": "c.csv",
            },
            [["id", "double"], ["2", "4"]],
        ),
    ],
    ids=("defaults", "custom_headers", "row_mapper"),
)
def test_stream_as_csv(qs, rows, kwargs, expected) -> None:
    out_name = kwargs.pop("filename")
    resp = stream_as_csv(qs(rows), out_name, **kwargs)

    text = "".join(c.decode() if isinstance(c, (bytes, bytearray)) else c for c in resp.streaming_content)
    got = list(csv.reader(io.StringIO(text)))

    assert resp.headers["Content-Disposition"] == content_disposition_header(True, out_name)
    assert got == expected
