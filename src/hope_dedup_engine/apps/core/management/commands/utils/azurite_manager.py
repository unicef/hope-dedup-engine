import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from django.conf import settings

from azure.storage.blob import BlobServiceClient, ContainerClient

logger = logging.getLogger(__name__)


class AzuriteManager:
    def __init__(self, container_name: str) -> None:
        """
        Initializes the AzuriteManager with the specified container and source path.

        Args:
            container_name (str): The name of the Azure Blob Storage container.
        """
        self.service_client: BlobServiceClient = (
            BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
        )
        self.container_client: ContainerClient = (
            self.service_client.get_container_client(container_name)
        )
        self._create_container()

    def _create_container(self) -> None:
        """
        Creates the container if it does not already exist.
        """
        try:
            if not self.container_client.exists():
                self.container_client.create_container()
                logger.info(
                    "Container '%s' created successfully.",
                    self.container_client.container_name,
                )
        except Exception:
            logger.exception("Failed to create container.")
            raise

    def list_files(self) -> list[str]:
        """
        Lists all files in the Azure Blob Storage container.

        Returns:
            list[str]: A list of blob names in the container.
        """
        try:
            blob_list = self.container_client.list_blobs()
            return [blob.name for blob in blob_list]
        except Exception:
            logger.exception("Failed to list files.")
            raise

    def _upload_file(self, file: Path) -> str:
        """
        Uploads a single file to the Azure Blob Storage container.

        Args:
            file (Path): The local path of the file to upload.
            images_src_path (Path | None): The local directory path where files are stored, or None if not specified.

        Returns:
            str: A message indicating the result of the upload.
        """
        if not file.exists():
            message = "File %s does not exist."
            logger.warning(message, file)
            return message % file
        try:
            blob_client = self.container_client.get_blob_client(file.name)
            with file.open("rb") as f:
                blob_client.upload_blob(f, overwrite=True)
                message = "File uploaded successfully! URL: %s"
                logger.debug(message, blob_client.url)
                return message % blob_client.url
        except Exception:
            logger.exception("Failed to upload file %s.", file)
            raise

    def upload_files(
        self, images_src_path: Path | None = None, batch_size: int = 250
    ) -> list[str]:
        """
        Uploads all files from the local directory to the Azure Blob Storage container.

        Args:
            batch_size (int, optional): The maximum number of concurrent uploads. Defaults to 250.

        Returns:
            list[str]: A list of messages indicating the result of each upload.
        """
        if images_src_path is None or not images_src_path.is_dir():
            message = "No valid directory provided for container '%s'."
            logger.warning(message, self.container_client.container_name)
            return [message % self.container_client.container_name]

        files = [f for f in images_src_path.glob("*.*") if f.is_file()]
        results: list[str] = []
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = {executor.submit(self._upload_file, f): f for f in files}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception:
                    file = futures[future]
                    results.append(f"Exception while processing {file}")
                    logger.exception("Exception while processing %s", file)
                    raise

        return results

    def delete_files(self) -> str:
        """
        Deletes all files in the Azure Blob Storage container.

        Returns:
            str: A message indicating the result of the deletion.
        """
        try:
            blob_names = self.list_files()
            failed_deletions = []

            for blob_name in blob_names:
                try:
                    self.container_client.delete_blob(blob_name)
                    logger.debug("Deleted blob: %s", blob_name)
                except Exception as e:
                    failed_deletions.append(blob_name)
                    logger.error(
                        "Failed to delete blob: %s. Error: %s", blob_name, str(e)
                    )

            if failed_deletions:
                message = f"Failed to delete the following blobs: {', '.join(failed_deletions)}"
            else:
                message = (
                    "All files deleted successfully!"
                    if blob_names
                    else "No files to delete."
                )

            logger.info(message)
            return message

        except Exception:
            logger.exception("Failed to delete files.")
            raise

    def delete_container(self) -> str:
        """
        Deletes the Azure Blob Storage container.

        Returns:
            str: A message indicating the result of the container deletion.
        """
        try:
            self.container_client.delete_container()
            message = "Container has been deleted successfully!"
            logger.info(message)
            return message
        except Exception:
            logger.exception("Failed to delete container.")
            raise
