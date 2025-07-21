from hope_dedup_engine.config.wsgi import application


def test_wsgi():
    assert application.request_class
