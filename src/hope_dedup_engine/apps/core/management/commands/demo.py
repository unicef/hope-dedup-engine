import logging
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import BaseCommand
from django.core.management.base import CommandError, SystemCheckError

from hope_dedup_engine.config import env

from .utils.azurite_manager import AzuriteManager

logger = logging.getLogger(__name__)


DEFAULT_DEMO_IMAGES = Path(__name__).resolve().parent / env("DEMO_IMAGES_PATH")
DEFAULT_DNN_FILES = Path(__name__).resolve().parent / env("DNN_FILES_PATH")


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
        The main logic for the command. Uploads files from the specified paths to Azure Blob Storage.

        Args:
            *args (Any): Positional arguments passed to the command.
            **options (dict[str, Any]): Keyword arguments including command-line options.
        """
        storages = {
            settings.AZURE_CONTAINER_HOPE: Path(options["demo_images"]),
            settings.AZURE_CONTAINER_DNN: Path(options["dnn_files"]),
            settings.AZURE_CONTAINER_HDE: None,
        }

        self.stdout.write(self.style.WARNING("Starting upload of files..."))
        for container_name, images_src_path in storages.items():
            try:
                am = AzuriteManager(container_name)
                if images_src_path:
                    am.upload_files(images_src_path)
                    logger.info(
                        "Uploaded files to container '%s' successfully.", container_name
                    )
                    self.stdout.write(
                        f"Successfully uploaded files to container: {container_name}"
                    )
            except (CommandError, SystemCheckError) as e:
                self.halt(e)
            except Exception as e:
                logger.exception("Error processing container '%s'", container_name)
                self.stdout.write(
                    self.style.ERROR(f"Error processing container {container_name}")
                )
                self.halt(e)

        self.stdout.write(self.style.SUCCESS("Finished uploading files."))

    def halt(self, e: Exception) -> None:
        """
        Handle an exception by logging the error and exiting the program.

        Args:
            e (Exception): The exception that occurred.
        """
        self.stdout.write(str(e), style_func=self.style.ERROR)
        self.stdout.write("\n\n***", style_func=self.style.ERROR)
        self.stdout.write("SYSTEM HALTED", style_func=self.style.ERROR)
        sys.exit(1)
