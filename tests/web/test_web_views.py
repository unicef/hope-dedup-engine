import pytest


def test_home(db, client):
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("url", ["/healthcheck/", "/healthcheck"])
def test_healthcheck(client, url):
    # this must not be reversed
    assert client.get(url).status_code == 200
