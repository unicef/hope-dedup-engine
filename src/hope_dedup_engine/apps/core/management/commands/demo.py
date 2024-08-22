import logging
import sys
from argparse import ArgumentParser
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
    "storage_success": "Files uploaded to storage '%s' successfully.",
    "success": "Finished uploading files to storage.",
    "failed": "Failed to upload files to storage '%s': %s",
    "unexpected": "An unexpected error occurred while uploading files to storage '%s': %s",
    "halted": "\n\n***\nSYSTEM HALTED",
}


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
        storages: dict[str, Path] = {
            "hope": Path(options["demo_images"]),
            "dnn": Path(options["dnn_files"]),
        }
        self.stdout.write(self.style.WARNING(MESSAGES["upload"]))
        logger.info(MESSAGES["upload"])

        try:
            for storage_name, images_src_path in storages.items():
                am = AzuriteManager(storage_name)
                if images_src_path is None:
                    continue
                if images_src_path.exists():
                    am.upload_files(images_src_path)
                else:
                    self.stdout.write(
                        self.style.ERROR(MESSAGES["not_exist"] % images_src_path)
                    )
                    logger.error(MESSAGES["not_exist"] % images_src_path)
                    self.halt(
                        FileNotFoundError(MESSAGES["not_exist"] % images_src_path)
                    )
                self.stdout.write(MESSAGES["storage_success"] % storage_name)
                logger.info(MESSAGES["storage_success"] % storage_name)
        except (CommandError, SystemCheckError) as e:
            self.stdout.write(self.style.ERROR(MESSAGES["failed"] % (storage_name, e)))
            logger.error(MESSAGES["failed"] % (storage_name, e))
            self.halt(e)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(MESSAGES["unexpected"] % (storage_name, e))
            )
            logger.exception(MESSAGES["unexpected"] % (storage_name, e))
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
