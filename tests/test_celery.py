from pytest_mock import MockerFixture

from hope_dedup_engine.config.celery import (
    app,
    init_sentry,
    on_task_postrun,
    reset_db_connection_pool,
)


def test_celery():
    assert app.clock


def test_init_celery():
    init_sentry()


def test_reset_db_connection_pool(mocker: MockerFixture) -> None:
    mock_connections = mocker.patch("django.db.connections")
    reset_db_connection_pool()
    mock_connections.close_all.assert_called_once()


def test_on_task_postrun(mocker: MockerFixture) -> None:
    mock_connections = mocker.patch("django.db.connections")
    on_task_postrun()
    mock_connections.close_all.assert_called_once()
