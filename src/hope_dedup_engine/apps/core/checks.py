from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.checks import Error, register

from storages.backends.azure_storage import AzureStorage

from hope_dedup_engine.config import env


@dataclass(frozen=True, slots=True)
class ErrorCode:
    id: str
    message: str
    hint: str


class StorageErrorCodes:  # pragma: no cover
    ENVIRONMENT_NOT_CONFIGURED = ErrorCode(
        id="hde.storage.E001",
        message="The environment variable '{storage}' is missing or improperly defined.",
        hint="Set the environment variable '{storage}'.\n\tExample: {storage}=storages.backends.azure_storage.AzureStorage?account_name=<name>&account_key=<key>&azure_container=<container>&overwrite_files=True",  # noqa: E501
    )
    STORAGE_CHECK_FAILED = ErrorCode(
        id="hde.storage.E002",
        message="Failed to access Azure storage due to incorrect data in the '{storage_name}' environment variable.",
        hint="Verify the '{storage_name}' variable and ensure that the provided parameters are accurate.\n\tExample: {storage_name}=storages.backends.azure_storage.AzureStorage?account_name=<name>&account_key=<key>&azure_container=<container>&overwrite_files=True",  # noqa: E501
    )
    FILE_NOT_FOUND = ErrorCode(
        id="hde.storage.E003",
        message="The file '{filename}' could not be found in the Azure storage specified by the environment variable '{storage_name}'.",  # noqa: E501
        hint="Ensure that the file '{filename}' exists in the storage. For details, refer to the documentation.",
    )


@register()
def example_check(app_configs, **kwargs: Any):  # pragma: no cover
    errors: list[Error] = []
    for t in settings.TEMPLATES:
        errors.extend(
            Error(
                f"'{d}' is not a directory",
                hint="Remove this directory from settings.TEMPLATES.",
                obj=settings,
                id="hde.E001",
            )
            for d in t["DIRS"]
            if not Path(d).is_dir()
        )
    return errors


@register(deploy=True)
def storages_check(app_configs: Any, **kwargs: Any) -> list[Error]:  # pragma: no cover
    """Check if the necessary environment variables for Azure storage are configured.

    Args:
        app_configs: Not used, but required by the checks framework.
        kwargs: Additional arguments passed by the checks framework.

    Returns:
        list[Error]: A list of Django Error objects, reporting missing environment variables,
                     missing files, or errors while accessing Azure storage containers.

    """
    storages = (
        "FILE_STORAGE_STATIC",
        "FILE_STORAGE_MEDIA",
    )

    errors = [
        Error(
            StorageErrorCodes.ENVIRONMENT_NOT_CONFIGURED.message.format(storage=storage),
            hint=StorageErrorCodes.ENVIRONMENT_NOT_CONFIGURED.hint.format(storage=storage),
            obj=storage,
            id=StorageErrorCodes.ENVIRONMENT_NOT_CONFIGURED.id,
        )
        for storage in storages
        if not env.storage(storage).get("OPTIONS")
    ]

    for storage_name in storages:
        options = env.storage(storage_name).get("OPTIONS")
        if options:
            try:
                storage = AzureStorage(**options)
                storage.client.exists()
            # we are collecting all possible errors here, so no need to treat them differently
            except Exception:  # noqa: BLE001
                errors.append(
                    Error(
                        StorageErrorCodes.STORAGE_CHECK_FAILED.message.format(storage_name=storage_name),
                        hint=StorageErrorCodes.STORAGE_CHECK_FAILED.hint.format(storage_name=storage_name),
                        obj=storage_name,
                        id=StorageErrorCodes.STORAGE_CHECK_FAILED.id,
                    )
                )

    return errors
