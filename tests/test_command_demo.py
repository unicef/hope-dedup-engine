from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError, SystemCheckError

import pytest
from pytest_mock import MockerFixture


@pytest.fixture()
def environment():
    return {
        "DEMO_IMAGES_PATH": "demo_images",
    }


@pytest.fixture
def mock_azurite_manager(mocker: MockerFixture):
    yield mocker.patch(
        "hope_dedup_engine.apps.core.management.commands.demo.AzuriteManager",
    )


def test_demo_handle_success(environment, mock_azurite_manager):
    out = StringIO()
    with (
        mock.patch.dict("os.environ", environment, clear=True),
        mock.patch("pathlib.Path.exists", return_value=True),
    ):
        call_command(
            "demo",
            demo_images="/path/to/demo/images",
            stdout=out,
        )
        assert "error" not in str(out.getvalue())
        assert "SYSTEM HALTED" not in out.getvalue()


@pytest.mark.parametrize(
    "side_effect, expected_exception",
    [
        (FileNotFoundError("File not found"), SystemExit),
        (CommandError("Command execution failed"), SystemExit),
        (SystemCheckError("System check failed"), SystemExit),
        (Exception("Unknown error"), SystemExit),
    ],
)
def test_demo_handle_exception(
    environment, mock_azurite_manager, side_effect, expected_exception
):
    mock_azurite_manager.side_effect = side_effect
    out = StringIO()
    with (
        mock.patch.dict("os.environ", environment, clear=True),
        pytest.raises(expected_exception),
    ):
        call_command("demo", stdout=out)

    assert "SYSTEM HALTED" in out.getvalue()
