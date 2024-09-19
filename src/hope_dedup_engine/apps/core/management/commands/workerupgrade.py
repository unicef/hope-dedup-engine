import logging
import sys
from argparse import ArgumentParser
from typing import Any, Final

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand
from django.core.management.base import CommandError, SystemCheckError

import requests
from storages.backends.azure_storage import AzureStorage

logger = logging.getLogger(__name__)


MESSAGES: Final[dict[str, str]] = {
    "already": "File '%s' already exists in FILE_STORAGE_DNN storage.",
    "process": "Downloading file from '%s' to '%s' in FILE_STORAGE_DNN storage...",
    "empty": "File at '%s' is empty (size is 0 bytes).",
    "halted": "\n\n***\nSYSTEM HALTED\nUnable to start without DNN files...",
}


class Command(BaseCommand):
    help = "Synchronizes DNN files from the git to azure storage"
    dnn_files = None

    def add_arguments(self, parser: ArgumentParser) -> None:
        """
        Adds custom command-line arguments to the management command.

        Args:
            parser (ArgumentParser): The argument parser instance to which the arguments should be added.

        Adds the following arguments:
            --force: A boolean flag that, when provided, forces the re-download of files even if they already exist
                    in Azure storage. Defaults to False.
            --deployfile-url (str): The URL from which the deploy (prototxt) file is downloaded.
                    Defaults to the value set in the project settings.
            --caffemodelfile-url (str): The URL from which the pre-trained model weights (caffemodel) are downloaded.
                    Defaults to the value set in the project settings.
            --download-timeout (int): The maximum time allowed for downloading files, in seconds.
                    Defaults to 3 minutes (180 seconds).
            --chunk-size (int): The size of each chunk to download in bytes. Defaults to 256 KB.
        """
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Force the re-download of files even if they already exist",
        )
        parser.add_argument(
            "--deployfile-url",
            type=str,
            default=settings.DNN_FILES.get("prototxt", {})
            .get("sources", {})
            .get("github"),
            help="The URL of the model architecture (deploy) file",
        )
        parser.add_argument(
            "--caffemodelfile-url",
            type=str,
            default=settings.DNN_FILES.get("caffemodel", {})
            .get("sources", {})
            .get("github"),
            help="The URL of the pre-trained model weights (caffemodel) file",
        )
        parser.add_argument(
            "--download-timeout",
            type=int,
            default=3 * 60,  # 3 minutes
            help="The timeout for downloading files",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=256 * 1024,  # 256 KB
            help="The size of each chunk to download in bytes",
        )

    def get_options(self, options: dict[str, Any]) -> None:
        self.verbosity = options["verbosity"]
        self.force = options["force"]
        self.dnn_files = (
            {
                "url": options["deployfile_url"],
                "filename": settings.DNN_FILES.get("prototxt", {})
                .get("sources", {})
                .get("azure"),
            },
            {
                "url": options["caffemodelfile_url"],
                "filename": settings.DNN_FILES.get("caffemodel", {})
                .get("sources", {})
                .get("azure"),
            },
        )
        self.download_timeout = options["download_timeout"]
        self.chunk_size = options["chunk_size"]

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Executes the command to download and store DNN files from a given source to Azure Blob Storage.

        Args:
            *args (Any): Positional arguments passed to the command.
            **options (dict[str, Any]): Keyword arguments passed to the command, including:
                - force (bool): If True, forces the re-download of files even if they already exist in storage.
                - deployfile_url (str): The URL of the DNN model architecture file to download.
                - caffemodelfile_url (str): The URL of the pre-trained model weights to download.
                - download_timeout (int): Timeout for downloading each file, in seconds.
                - chunk_size (int): The size of chunks for streaming downloads, in bytes.

        Raises:
            FileNotFoundError: If the downloaded file is empty (size is 0 bytes).
            ValidationError: If any arguments are invalid or improperly configured.
            CommandError: If an issue occurs with the Django command execution.
            SystemCheckError: If a system check error is encountered during execution.
            Exception: For any other errors that occur during the download or storage process.
        """
        self.get_options(options)
        if self.verbosity >= 1:
            echo = self.stdout.write
        else:
            echo = lambda *a, **kw: None  # noqa: E731

        try:
            dnn_storage = AzureStorage(**settings.STORAGES.get("dnn").get("OPTIONS"))
            _, files = dnn_storage.listdir("")
            for file in self.dnn_files:
                if self.force or not file.get("filename") in files:
                    echo(MESSAGES["process"] % (file.get("url"), file.get("filename")))
                    with requests.get(
                        file.get("url"), stream=True, timeout=self.download_timeout
                    ) as r:
                        r.raise_for_status()
                        if int(r.headers.get("Content-Length", 1)) == 0:
                            raise FileNotFoundError(MESSAGES["empty"] % file.get("url"))
                        with dnn_storage.open(file.get("filename"), "wb") as f:
                            for chunk in r.iter_content(chunk_size=self.chunk_size):
                                f.write(chunk)
                else:
                    echo(MESSAGES["already"] % file.get("filename"))
        except ValidationError as e:
            self.halt(Exception("\n- ".join(["Wrong argument(s):", *e.messages])))
        except (CommandError, FileNotFoundError, SystemCheckError) as e:
            self.halt(e)
        except Exception as e:
            self.halt(e)

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
