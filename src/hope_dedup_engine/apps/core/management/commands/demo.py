import logging
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from django.core.management import BaseCommand
from django.core.management.base import CommandError, SystemCheckError

from hope_dedup_engine.config import env

from .utils.azurite_manager import AzuriteManager

logger = logging.getLogger(__name__)


BASE_PATH: Final[Path] = (
    Path(__file__).resolve().parents[6] / "tests" / "extras" / "demoapp"
)
DEFAULT_DEMO_IMAGES: Final[Path] = BASE_PATH / env("DEMO_IMAGES_PATH")
DEFAULT_DNN_FILES: Final[Path] = BASE_PATH / env("DNN_FILES_PATH")

MESSAGES: Final[dict[str, str]] = {
    "upload": "Starting upload of files...",
    "not_exist": "Directory '%s' does not exist.",
    "container_success": "Container for storage '%s' created successfully.",
    "storage_success": "Files uploaded to storage '%s' successfully.",
    "success": "Finished uploading files to storage.",
    "failed": "Failed to upload files to storage '%s': %s",
    "unexpected": "An unexpected error occurred while uploading files to storage '%s': %s",
    "halted": "\n\n***\nSYSTEM HALTED",
}


@dataclass(frozen=True)
class Storage:
    name: str
    src: Path | None = field(default=None)
    options: dict[str, str] = field(default_factory=dict)


class Command(BaseCommand):
    help = "Create demo app"

    def add_arguments(self, parser: ArgumentParser) -> None:
        """
        Define the command-line arguments that this command accepts.

        Args:
            parser (ArgumentParser): The parser for command-line arguments.
        """
        parser.add_argument(
            "--demo-images",
            type=str,
            default=str(DEFAULT_DEMO_IMAGES),
            help="Path to the demo images directory",
        )
        parser.add_argument(
            "--dnn-files",
            type=str,
            default=str(DEFAULT_DNN_FILES),
            help="Path to the DNN files directory",
        )

    def handle(self, *args: Any, **options: dict[str, Any]) -> None:
        """
        Main logic for handling the command to create containers and upload files to Azurite Storage.

        Args:
            *args (Any): Positional arguments passed to the command.
            **options (dict[str, Any]): Keyword arguments including command-line options.

        Raises:
            FileNotFoundError: If a specified directory does not exist.
            CommandError: If a Django management command error occurs.
            SystemCheckError: If a Django system check error occurs.
            Exception: For any other unexpected errors that may arise during the execution of the command.

        """
        storages = (
            Storage(name="hope", src=Path(options["demo_images"])),
            Storage(name="dnn", src=Path(options["dnn_files"])),
            Storage(name="media"),
            Storage(name="staticfiles", options={"public_access": "blob"}),
        )
        self.stdout.write(self.style.WARNING(MESSAGES["upload"]))
        logger.info(MESSAGES["upload"])

        for storage in storages:
            try:
                am = AzuriteManager(storage.name, storage.options)
                self.stdout.write(MESSAGES["container_success"] % storage.name)
                if storage.src is None:
                    continue
                if storage.src.exists():
                    am.upload_files(storage.src)
                else:
                    self.stdout.write(
                        self.style.ERROR(MESSAGES["not_exist"] % storage.src)
                    )
                    logger.error(MESSAGES["not_exist"] % storage.src)
                    self.halt(FileNotFoundError(MESSAGES["not_exist"] % storage.src))
                self.stdout.write(MESSAGES["storage_success"] % storage.name)
                logger.info(MESSAGES["storage_success"] % storage.name)
            except (CommandError, SystemCheckError) as e:
                self.stdout.write(
                    self.style.ERROR(MESSAGES["failed"] % (storage.name, e))
                )
                logger.error(MESSAGES["failed"] % (storage.name, e))
                self.halt(e)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(MESSAGES["unexpected"] % (storage.name, e))
                )
                logger.exception(MESSAGES["unexpected"] % (storage.name, e))
                self.halt(e)

        self.stdout.write(self.style.SUCCESS(MESSAGES["success"]))

    def halt(self, e: Exception) -> None:
        """
        Handle an exception by logging the error and exiting the program.

        Args:
            e (Exception): The exception that occurred.
        """
        logger.exception(e)
        self.stdout.write(str(e), style_func=self.style.ERROR)
        self.stdout.write(MESSAGES["halted"], style_func=self.style.ERROR)
        sys.exit(1)
