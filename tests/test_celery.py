from hope_dedup_engine.config.celery import app
from hope_dedup_engine.config.celery import init_sentry


def test_celery():
    assert app.clock


def test_init_celery():
    init_sentry()
