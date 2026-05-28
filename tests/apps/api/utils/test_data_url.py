import pytest

from hope_dedup_engine.apps.api.utils.data_url import ParsedDataURL, parse_data_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("data:media-type;base64,data", ParsedDataURL(mimetype="media-type", encoding="base64", content="data")),
        ("data:media-type;base64,", ParsedDataURL(mimetype="media-type", encoding="base64", content="")),
        ("data:media-type;,data", ParsedDataURL(mimetype="media-type", encoding=None, content=",data")),
        ("data:media-type;data", ParsedDataURL(mimetype="media-type", encoding=None, content="data")),
        ("data:media-type;other,data", ParsedDataURL(mimetype="media-type", encoding=None, content="other,data")),
        ("data:;base64,data", ParsedDataURL(mimetype=None, encoding="base64", content="data")),
        (":media-type;base64,data", None),
        ("other:media-type;base64,data", None),
        (";base64,data", None),
        ("data:media-type;", ParsedDataURL(mimetype="media-type", encoding=None, content="")),
        ("", None),
    ],
)
def test_data_url(url: str, expected: ParsedDataURL | None) -> None:
    assert parse_data_url(url) == expected
