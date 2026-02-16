import pytest

from hope_dedup_engine.apps.api.utils.data_url import ParsedDataURL, parse_data_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("", None),
        ("data:media-type;base64,data", ParsedDataURL(mimetype="media-type", encoding="base64", content="data")),
    ],
)
def test_data_url(url: str, expected: ParsedDataURL | None) -> None:
    assert parse_data_url(url) == expected
