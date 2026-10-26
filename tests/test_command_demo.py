from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError, SystemCheckError

import pytest
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.core.management.commands import demo


@pytest.fixture
def environment():
    return {
        "DEMO_IMAGES_PATH": "demo_images",
    }


@pytest.fixture
def mock_azurite_manager(mocker: MockerFixture):
    return mocker.patch(
        "hope_dedup_engine.apps.core.management.commands.demo.AzuriteManager",
    )


def _patch_storage_source(mocker: MockerFixture, src: Path) -> None:
    """Make every storage declare `src` as its source directory."""
    real_storage = demo.Storage

    def _factory(name: str, options: dict[str, str] | None = None) -> demo.Storage:
        return real_storage(name=name, src=src, options=options or {})

    mocker.patch(
        "hope_dedup_engine.apps.core.management.commands.demo.Storage",
        side_effect=_factory,
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
    ("side_effect", "expected_exception"),
    [
        (FileNotFoundError("File not found"), SystemExit),
        (CommandError("Command execution failed"), SystemExit),
        (SystemCheckError("System check failed"), SystemExit),
        (Exception("Unknown error"), SystemExit),
    ],
)
def test_demo_handle_exception(environment, mock_azurite_manager, side_effect, expected_exception):
    mock_azurite_manager.side_effect = side_effect
    out = StringIO()
    with (
        mock.patch.dict("os.environ", environment, clear=True),
        pytest.raises(expected_exception),
    ):
        call_command("demo", stdout=out)

    assert "SYSTEM HALTED" in out.getvalue()


def test_demo_handle_uploads_the_source_files(environment, mock_azurite_manager, mocker, tmp_path):
    """A storage with a source directory uploads its files and reports success."""
    _patch_storage_source(mocker, tmp_path)
    out = StringIO()

    with mock.patch.dict("os.environ", environment, clear=True):
        call_command("demo", stdout=out)

    assert mock_azurite_manager.return_value.upload_files.call_count == 2
    assert mock_azurite_manager.return_value.upload_files.call_args_list == [
        mock.call(tmp_path),
        mock.call(tmp_path),
    ]
    assert "Files uploaded to storage 'media' successfully." in out.getvalue()
    assert "Finished uploading files to storage." in out.getvalue()
    assert "SYSTEM HALTED" not in out.getvalue()


def test_demo_handle_missing_source_directory(environment, mock_azurite_manager, mocker, tmp_path):
    """A storage pointing to a missing directory halts the command."""
    missing = tmp_path / "missing"
    _patch_storage_source(mocker, missing)
    out = StringIO()

    with (
        mock.patch.dict("os.environ", environment, clear=True),
        pytest.raises(SystemExit),
    ):
        call_command("demo", stdout=out)

    assert f"Directory '{missing}' does not exist." in out.getvalue()
    assert "SYSTEM HALTED" in out.getvalue()
    mock_azurite_manager.return_value.upload_files.assert_not_called()
