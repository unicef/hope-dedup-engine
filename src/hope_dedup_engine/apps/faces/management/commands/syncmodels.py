import logging
import sys
from typing import Any, Final

from django.conf import settings
from django.core.management import BaseCommand
from django.core.management.base import CommandError, SystemCheckError

from hope_dedup_engine.apps.faces.managers.file_sync import FileSyncManager

logger = logging.getLogger(__name__)


MESSAGES: Final[dict[str, str]] = {
    "sync": "Starting synchronization of models pre-trained-weights files from github to '%s'.",
    "success": "Finished synchronizing models pre-trained-weights files successfully.",
    "failed": "Failed to synchronize models pre-trained-weights files.",
    "halted": "\n\n***\nSYSTEM HALTED\nUnable to start without models pre-trained-weights files...",
    "progress": "\rDownloading file '%s': %s",
}


class Command(BaseCommand):
    """
    Command ensures that the necessary pre-trained weights are downloaded and stored locally.
    If the weights are already present, the command can be forced to re-download the files.

    Arguments:
        --force: If provided, forces the re-download of files, even if they already exist locally.
    """

    help = "Synchronizes models pre-trained-weights files from the specified source to shared volume"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Force the re-download of files even if they already exist locally",
        )

    def handle(self, *args: Any, **options: dict[str, Any]) -> None:
        """
        Args:
            *args: Variable length argument list.
            **options: Dictionary of command line options passed to the command.

        This method initiates the synchronization, providing a progress update for each file download.
        If an error occurs, it logs the error and halts the execution with an appropriate message.
        """

        def on_progress(filename: str, percent: int, is_complete: bool = False) -> None:
            """
            Prints the progress of the file download in the terminal.

            Args:
                filename (str): The name of the file being downloaded.
                percent (int): The download progress as a percentage.
                is_complete (bool, optional): Whether the download is complete. Defaults to False.
            """
            self.stdout.write(MESSAGES["progress"] % (filename, percent), ending="")
            if is_complete:
                self.stdout.write("\n")

        self.stdout.write(
            self.style.WARNING(
                MESSAGES["sync"] % settings.DEEPFACE_WEIGHTS_BASE_LOCATION
            )
        )
        logger.info(MESSAGES["sync"] % settings.DEEPFACE_WEIGHTS_BASE_LOCATION)

        try:
            downloader = FileSyncManager(
                source="github",
                local_base_location=settings.DEEPFACE_WEIGHTS_BASE_LOCATION,
            ).downloader
            for filename, url in settings.DEEPFACE_WEIGHTS.items():
                result = downloader.sync(
                    filename,
                    url,
                    force=options.get("force"),
                    on_progress=on_progress,
                )
                on_progress(filename, result, is_complete=True)
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
