import os
from io import StringIO
from unittest import mock

from django.core.management import call_command

import pytest
from pytest_mock import MockerFixture


@pytest.fixture()
def environment():
    return {
        "DEMO_IMAGES_PATH": "demo_images",
        "DNN_FILES_PATH": "dnn_files",
    }


@pytest.fixture
def mock_azurite_manager(mocker: MockerFixture):
    with mock.patch(
        "hope_dedup_engine.apps.core.management.commands.utils.azurite_manager.AzuriteManager"
    ) as MockAzuriteManager:
        yield MockAzuriteManager


def test_demo_handle_success(environment, mock_azurite_manager):
    out = StringIO()
    with (
        mock.patch.dict("os.environ", environment, clear=True),
        mock.patch("pathlib.Path.exists", return_value=True),
    ):
        call_command(
            "demo",
            demo_images="/path/to/demo/images",
            dnn_files="/path/to/dnn/files",
            stdout=out,
        )
        assert "error" not in str(out.getvalue())
        assert mock_azurite_manager.call_count == 4
        assert mock_azurite_manager.return_value.upload_files.call_count == 2


def test_demo_handle_exception(environment, mock_azurite_manager):
    mock_azurite_manager.side_effect = Exception()
    with mock.patch.dict(os.environ, environment, clear=True):
        with pytest.raises(Exception):
            call_command("demo", ignore_errors=False)
