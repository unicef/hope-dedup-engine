import logging
import sys
from typing import Any, Final

from django.conf import settings
from django.core.management import BaseCommand
from django.core.management.base import CommandError, SystemCheckError

from constance import config

from hope_dedup_engine.apps.faces.managers.file_sync import FileSyncManager

logger = logging.getLogger(__name__)


MESSAGES: Final[dict[str, str]] = {
    "sync": "Starting synchronization of DNN files from %s ...",
    "success": "Finished synchronizing DNN files successfully.",
    "failed": "Failed to synchronize DNN files.",
    "halted": "\n\n***\nSYSTEM HALTED\nUnable to start without DNN files...",
}


class Command(BaseCommand):
    help = "Synchronizes DNN files from the specified source to local storage"

    def add_arguments(self, parser):
        """
        Adds custom command-line arguments to the management command.

        Args:
            parser (argparse.ArgumentParser): The argument parser instance to which the arguments should be added.

        Adds the following arguments:
            --force: A boolean flag that, when provided, forces the re-download of files even if they
                    already exist locally. Defaults to False.
            --source (str): Specifies the source from which to download the DNN files. The available choices
                            are dynamically retrieved from the CONSTANCE_ADDITIONAL_FIELDS configuration.
                            Defaults to the value of config.DNN_FILES_SOURCE.
        """
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Force the re-download of files even if they already exist locally",
        )
        parser.add_argument(
            "--source",
            type=str,
            default=config.DNN_FILES_SOURCE,
            choices=tuple(
                ch[0]
                for ch in settings.CONSTANCE_ADDITIONAL_FIELDS.get("dnn_files_source")[
                    1
                ].get("choices")
            ),
            help="The source from which to download the DNN files",
        )

    def handle(self, *args: Any, **options: dict[str, Any]) -> None:
        """
        Executes the command to synchronize DNN files from a specified source to local storage.

        Args:
            *args (Any): Positional arguments passed to the command.
            **options (dict[str, Any]): Keyword arguments passed to the command, including:
                - force (bool): If True, forces the re-download of files even if they already exist locally.
                - source (str): The source from which to download the DNN files.

        Raises:
            CommandError: If there is a problem executing the command.
            SystemCheckError: If there is a system check error.
            Exception: For any other errors that occur during execution.
        """

        def on_progress(filename: str, percent: int, is_complete: bool = False) -> None:
            """
            Callback function to report the progress of a file download.

            Args:
                filename (str): The name of the file being downloaded.
                percent (int): The current download progress as a percentage (0-100).
                is_complete (bool): If True, indicates that the download is complete. Defaults to False.

            Returns:
                None
            """
            self.stdout.write(f"\rDownloading file {filename}: {percent}%", ending="")
            if is_complete:
                self.stdout.write("\n")

        self.stdout.write(self.style.WARNING(MESSAGES["sync"]) % options.get("source"))
        logger.info(MESSAGES["sync"])

        try:
            downloader = FileSyncManager(options.get("source")).downloader
            for _, info in settings.DNN_FILES.items():
                downloader.sync(
                    info.get("filename"),
                    info.get("sources").get(options.get("source")),
                    force=options.get("force"),
                    on_progress=on_progress,
                )
                on_progress(info.get("filename"), 100, is_complete=True)
        except (CommandError, SystemCheckError) as e:
            self.halt(e)
        except Exception as e:
            self.stdout.write(self.style.ERROR(MESSAGES["failed"]))
            logger.error(MESSAGES["failed"])
            self.halt(e)

        self.stdout.write(self.style.SUCCESS(MESSAGES["success"]))

    def halt(self, e: Exception) -> None:
        """
        Handle an exception by logging the error and exiting the program.

        Args:
            e (Exception): The exception that occurred.
        """
        logger.exception(e)
        self.stdout.write(self.style.ERROR(str(e)))
        self.stdout.write(self.style.ERROR(MESSAGES["halted"]))
        sys.exit(1)
