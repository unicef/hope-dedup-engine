import logging
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Final

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand, call_command
from django.core.management.base import CommandError, SystemCheckError
from django.core.validators import validate_email
from django.contrib.auth import get_user_model

from hope_dedup_engine.apps.security.constants import DEFAULT_GROUP_NAME
from hope_dedup_engine.config import env

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Echo(Protocol):
    def __call__(self, msg: str, style_func: Callable[[str], str] | None = ...) -> None: ...


logger = logging.getLogger(__name__)

FALLBACK_EMAIL_DOMAIN: Final[str] = "example.org"


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

    def _ensure_superuser(self, user: Any) -> bool:
        if user.is_staff and user.is_superuser:
            return False
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        return True

    def _run_createsuperuser(self, username: str, email: str) -> bool:
        os.environ["DJANGO_SUPERUSER_USERNAME"] = username
        os.environ["DJANGO_SUPERUSER_EMAIL"] = email

        if password := self.admin_password if username == self.admin_email else "":
            os.environ["DJANGO_SUPERUSER_PASSWORD"] = password
        else:
            os.environ.pop("DJANGO_SUPERUSER_PASSWORD", None)

        call_command(
            "createsuperuser",
            email=email,
            username=username,
            verbosity=max(self.verbosity - 1, 0),
            interactive=False,
        )
        return bool(password)

    def _superuser_logins(self) -> list[str]:
        raw = [self.admin_email, *self.superusers]
        return list(dict.fromkeys(s for x in raw if x and (s := x.strip())))

    def _create_superusers(self, echo: Any) -> None:
        users = get_user_model().objects

        for login in self._superuser_logins():
            email = login if "@" in login else f"{login}@{FALLBACK_EMAIL_DOMAIN}"

            if user := (
                (users.filter(email=email).first() if "@" in login else None) or users.filter(username=login).first()
            ):
                changed = self._ensure_superuser(user)
                echo(
                    f"{'Granted superuser privileges' if changed else 'User found, skip'}: {login}",
                    style_func=self.style.WARNING,
                )
                continue

            validate_email(email)
            password_provided = self._run_createsuperuser(login, email)

            echo(
                f"Created superuser: {email}{'' if password_provided else ' with unusable password'}",
                style_func=self.style.WARNING,
            )

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
        parser.add_argument(
            "--superusers",
            nargs="+",
            dest="superusers",
            default=None,
            help="Emails/usernames to grant superuser privileges (space-separated)",
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
        self.superusers = options["superusers"] if options["superusers"] is not None else env("SUPERUSERS", [])

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
            self._create_superusers(echo)
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
