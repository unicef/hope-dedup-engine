from io import StringIO
from typing import Final
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError, SystemCheckError

import pytest
from pytest_mock import MockerFixture

DNN_FILES: Final[tuple[dict[str, str]]] = (
    {"url": "http://example.com/file1", "filename": "file1"},
    {"url": "http://example.com/file2", "filename": "file2"},
)


@pytest.fixture
def mock_requests_get():
    with mock.patch("requests.get") as mock_get:
        mock_response = mock_get.return_value.__enter__.return_value
        mock_response.iter_content.return_value = [b"Hello, world!"] * 3
        mock_response.raise_for_status = lambda: None
        yield mock_get


@pytest.fixture
def mock_azurite_manager(mocker: MockerFixture):
    yield mocker.patch(
        "hope_dedup_engine.apps.core.management.commands.workerupgrade.AzureStorage",
    )


@pytest.fixture
def mock_dnn_files(mocker: MockerFixture):
    yield mocker.patch(
        "hope_dedup_engine.apps.core.management.commands.workerupgrade.Command.dnn_files",
        new_callable=mocker.PropertyMock,
    )


@pytest.mark.parametrize(
    "force, expected_count, existing_files",
    [
        (False, 2, []),
        (False, 1, [DNN_FILES[0]["filename"]]),
        (False, 0, [f["filename"] for f in DNN_FILES][:2]),
        (True, 2, []),
        (True, 2, [DNN_FILES[0]["filename"]]),
        (True, 2, [f["filename"] for f in DNN_FILES][:2]),
    ],
)
def test_workerupgrade_handle_success(
    mock_requests_get,
    mock_azurite_manager,
    mock_dnn_files,
    force,
    expected_count,
    existing_files,
):
    mock_dnn_files.return_value = DNN_FILES
    mock_azurite_manager().listdir.return_value = ([], existing_files)
    out = StringIO()

    call_command("workerupgrade", stdout=out, force=force)

    assert "SYSTEM HALTED" not in out.getvalue()
    assert mock_requests_get.call_count == expected_count
    assert mock_azurite_manager().open.call_count == expected_count


@pytest.mark.parametrize(
    "side_effect, expected_exception",
    [
        (FileNotFoundError("File not found"), SystemExit),
        (ValidationError("Invalid argument"), SystemExit),
        (CommandError("Command execution failed"), SystemExit),
        (SystemCheckError("System check failed"), SystemExit),
        (Exception("Unknown error"), SystemExit),
    ],
)
def test_workerupgrade_handle_exception(
    mock_requests_get, mock_azurite_manager, side_effect, expected_exception
):
    mock_azurite_manager.side_effect = side_effect
    out = StringIO()
    with pytest.raises(expected_exception):
        call_command("workerupgrade", stdout=out)

    assert "SYSTEM HALTED" in out.getvalue()
