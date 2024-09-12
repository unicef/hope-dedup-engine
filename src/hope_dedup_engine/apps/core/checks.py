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
        message="Environment variable '{storage}' is improperly configured.",
        hint="Set the environment variable '{storage}'.",
    )
    FILE_NOT_FOUND = ErrorCode(
        id="hde.storage.E002",
        message="File '{filename}' not found in {storage_name} Azure storage.",
        hint="Check that the file '{filename}' exists in the storage.",
    )
    STORAGE_CHECK_FAILED = ErrorCode(
        id="hde.storage.E003",
        message="Error while checking Azure storage: {storage_name}.",
        hint="Check the {storage_name} storage settings.",
    )


@register()
def example_check(app_configs, **kwargs: Any):
    errors = []
    for t in settings.TEMPLATES:
        for d in t["DIRS"]:
            if not Path(d).is_dir():
                errors.append(
                    Error(
                        f"'{d}' is not a directory",
                        hint="Remove this directory from settings.TEMPLATES.",
                        obj=settings,
                        id="hde.E001",
                    )
                )
    return errors


@register()
def storages_check(app_configs: Any, **kwargs: Any) -> list[Error]:  # pragma: no cover
    """
    Checks if the necessary environment variables for Azure storage are configured
    and verifies the presence of required files in the specified Azure storage containers.

    Args:
        app_configs: Not used, but required by the checks framework.
        kwargs: Additional arguments passed by the checks framework.

    Returns:
        list[Error]: A list of Django Error objects, reporting missing environment variables,
                     missing files, or errors while accessing Azure storage containers.
    """
    storages = ("FILE_STORAGE_DNN", "FILE_STORAGE_HOPE")

    errors = [
        Error(
            StorageErrorCodes.ENVIRONMENT_NOT_CONFIGURED.message.format(
                storage=storage
            ),
            hint=StorageErrorCodes.ENVIRONMENT_NOT_CONFIGURED.hint.format(
                storage=storage
            ),
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
                _, files = storage.listdir()
                if storage_name == "FILE_STORAGE_DNN":
                    for _, info in settings.DNN_FILES.items():
                        filename = info.get("filename")
                        if filename not in files:
                            errors.append(
                                Error(
                                    StorageErrorCodes.FILE_NOT_FOUND.message.format(
                                        filename=filename, storage_name=storage_name
                                    ),
                                    hint=StorageErrorCodes.FILE_NOT_FOUND.hint.format(
                                        filename=filename
                                    ),
                                    obj=f"{storage_name}/{filename}",
                                    id=StorageErrorCodes.FILE_NOT_FOUND.id,
                                )
                            )
            except Exception:
                errors.append(
                    Error(
                        StorageErrorCodes.STORAGE_CHECK_FAILED.message.format(
                            storage_name=storage_name
                        ),
                        hint=StorageErrorCodes.STORAGE_CHECK_FAILED.hint.format(
                            storage_name=storage_name
                        ),
                        obj=storage_name,
                        id=StorageErrorCodes.STORAGE_CHECK_FAILED.id,
                    )
                )

    return errors
