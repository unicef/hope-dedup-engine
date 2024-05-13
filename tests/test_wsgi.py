import pytest


def test_wsgi():
    try:
        from hope_dedup_engine.config.wsgi import application

        assert application.request_class
    except Exception as e:
        pytest.fail(e)
