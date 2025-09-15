import logging
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand, call_command
from django.core.management.base import CommandError, SystemCheckError
from django.core.validators import validate_email

# azure storage support
try:
    from azure.core.exceptions import ResourceExistsError
    from azure.storage.blob import CorsRule
    from django.contrib.staticfiles.storage import staticfiles_storage
    from storages.backends.azure_storage import AzureStorage
except ImportError:
    AzureStorage = None  # type: ignore
    ResourceExistsError = None  # type: ignore
    staticfiles_storage = None  # type: ignore
    CorsRule = None  # type: ignore


from hope_dedup_engine.apps.security.constants import DEFAULT_GROUP_NAME
from hope_dedup_engine.apps.security.models import User
from hope_dedup_engine.config import env

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Echo(Protocol):
    def __call__(self, msg: str, style_func: Callable[[str], str] | None = ...) -> None: ...


logger = logging.getLogger(__name__)


def noop(*_: Any, **__: Any) -> None:
    pass


class Command(BaseCommand):
    requires_migrations_checks = False
    requires_system_checks = []

    def _run_env(self) -> None:
        call_command("env", check=True)

    def _run_check(self) -> None:
        if self.run_check:
            call_command("check", deploy=True, verbosity=self.verbosity - 1)

    def _run_syncmodels(self, echo: Echo) -> None:
        if self.sync_models:
            echo("Run sync pre-trained models")
            call_command("syncmodels", verbosity=self.verbosity - 1)

    def _run_collectstatic(self, echo: Echo, extra: Mapping[str, Any]) -> None:
        if self.static:
            if AzureStorage and ResourceExistsError:
                storages_to_configure = [
                    AzureStorage(**config.get("OPTIONS"))
                    for config in settings.STORAGES.values()
                    if "storages.backends.azure_storage.AzureStorage" in config.get("BACKEND", "")
                ]
                if storages_to_configure:
                    # Configure CORS once on the service client.
                    if not CorsRule:
                        raise CommandError(
                            "'azure-storage-blob' is not installed, which is required for CORS configuration. "
                            "Please run: uv pip install 'django-storages[azure]'"
                        )
                    echo("Configuring CORS for Azure Storage.")
                    cors_rule = CorsRule(
                        allowed_origins=["*"],
                        allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "POST", "DELETE"],
                        allowed_headers=["*"],
                        exposed_headers=["*"],
                        max_age_in_seconds=86400,
                    )
                    storages_to_configure[0].service_client.set_service_properties(cors=[cors_rule])
                    echo("CORS for Azure Storage configured to allow all origins.")

                    # Ensure all containers exist.
                    for storage in storages_to_configure:
                        echo(f"Ensuring Azure Storage container '{storage.azure_container}' exists.")
                        try:
                            container_client = storage.service_client.get_container_client(storage.azure_container)
                            container_client.create_container()
                            echo(f"Container '{storage.azure_container}' created.")
                        except ResourceExistsError:
                            echo(f"Container '{storage.azure_container}' already exists.")

            static_root = Path(env("STATIC_ROOT"))
            echo(f"Run collectstatic to: '{static_root}' - '{static_root.absolute()}")
            if not static_root.exists():
                static_root.mkdir(parents=True)
            call_command("collectstatic", **extra)

    def _run_migrate(self, echo: Echo, extra: Mapping[str, Any]) -> None:
        if self.migrate:
            echo("Run migrations")
            call_command("migrate", **extra)
            call_command("create_extra_permissions")

    def _run_remove_stale_contenttypes(self, echo: Echo, extra: Mapping[str, Any]) -> None:
        echo("Remove stale contenttypes")
        call_command("remove_stale_contenttypes", **extra)

    def _create_superuser(self, echo: Echo) -> None:
        if self.admin_email:
            if User.objects.filter(email=self.admin_email).exists():
                echo(
                    f"User {self.admin_email} found, skip creation",
                    style_func=self.style.WARNING,
                )
            else:
                echo(
                    f"Creating superuser: {self.admin_email}",
                    style_func=self.style.WARNING,
                )
                validate_email(self.admin_email)
                os.environ["DJANGO_SUPERUSER_USERNAME"] = self.admin_email
                os.environ["DJANGO_SUPERUSER_EMAIL"] = self.admin_email
                os.environ["DJANGO_SUPERUSER_PASSWORD"] = self.admin_password
                call_command(
                    "createsuperuser",
                    email=self.admin_email,
                    username=self.admin_email,
                    verbosity=self.verbosity - 1,
                    interactive=False,
                )

            admin = User.objects.get(email=self.admin_email)
        else:
            admin = User.objects.filter(is_superuser=True).first()

        if not admin:
            raise CommandError("Failure: Error when creating an admin user!")

    def _create_groups(self) -> None:
        Group.objects.get_or_create(name="Admins")
        Group.objects.get_or_create(name=DEFAULT_GROUP_NAME)

    def add_arguments(self, parser: "ArgumentParser") -> None:
        parser.add_argument(
            "--with-check",
            action="store_true",
            dest="check",
            help="Run checks",
        )
        parser.add_argument(
            "--no-check",
            action="store_false",
            dest="check",
            default=False,
            help="Do not run checks",
        )
        parser.add_argument(
            "--no-migrate",
            action="store_false",
            dest="migrate",
            default=True,
            help="Do not run migrations",
        )
        parser.add_argument(
            "--prompt",
            action="store_true",
            dest="prompt",
            default=False,
            help="Let ask for confirmation",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            dest="debug",
            default=False,
            help="debug mode",
        )
        parser.add_argument(
            "--no-static",
            action="store_false",
            dest="static",
            default=True,
            help="Do not run collectstatic",
        )
        parser.add_argument(
            "--no-sync-models",
            action="store_false",
            dest="sync_models",
            default=True,
            help="Do not sync pre-trained models",
        )
        parser.add_argument(
            "--admin-email",
            action="store",
            dest="admin_email",
            default="",
            help="Admin email",
        )
        parser.add_argument(
            "--admin-password",
            action="store",
            dest="admin_password",
            default="",
            help="Admin password",
        )

    def get_options(self, options: dict[str, Any]) -> None:
        self.verbosity = options["verbosity"]
        self.run_check = options["check"]
        self.prompt = not options["prompt"]
        self.static = options["static"]
        self.migrate = options["migrate"]
        self.sync_models = options["sync_models"]
        self.debug = options["debug"]

        self.admin_email = str(options["admin_email"] or env("ADMIN_EMAIL", ""))
        self.admin_password = str(options["admin_password"] or env("ADMIN_PASSWORD", ""))

    def halt(self, e: Exception) -> None:
        self.stdout.write(str(e), style_func=self.style.ERROR)
        self.stdout.write("\n\n***", style_func=self.style.ERROR)
        self.stdout.write("SYSTEM HALTED", style_func=self.style.ERROR)
        self.stdout.write("Unable to start...", style_func=self.style.ERROR)
        if self.debug:
            raise e

        sys.exit(1)

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: C901
        self.get_options(options)
        echo = self.stdout.write if self.verbosity >= 1 else noop

        try:
            extra = {
                "no_input": not self.prompt,
                "verbosity": self.verbosity - 1,
                "stdout": self.stdout,
            }
            echo("Running upgrade", style_func=self.style.WARNING)

            self._run_env()
            self._run_check()
            self._run_syncmodels(echo)
            self._run_collectstatic(echo, extra)
            self._run_migrate(echo, extra)
            self._run_remove_stale_contenttypes(echo, extra)
            self._create_superuser(echo)
            self._create_groups()

            echo("Upgrade completed", style_func=self.style.SUCCESS)
        except ValidationError as e:
            self.halt(Exception("\n- ".join(["Wrong argument(s):", *e.messages])))
        except (CommandError, SystemCheckError) as e:
            self.halt(e)
        except Exception as e:
            self.stdout.write(str(e), style_func=self.style.ERROR)
            logger.exception(e)
            self.halt(e)
